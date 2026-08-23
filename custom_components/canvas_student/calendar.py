import asyncio
import logging

import aiohttp
import homeassistant.util.dt as dt_util

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_BASE_URL, CONF_ACCESS_TOKEN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    user_name = coordinator.data.get("name", "Student")
    entities = [
        CanvasCalendarEntity(
            coordinator, hass, entry, "all", f"{user_name} Calendar"
        )
    ]

    for course in coordinator.data.get("courses", []):
        if not isinstance(course, dict) or "id" not in course:
            continue

        course_name = course.get("course_code") or course.get("name")
        if not course_name:
            continue

        entities.append(
            CanvasCalendarEntity(
                coordinator,
                hass,
                entry,
                course["id"],
                f"{user_name} {course_name} Calendar",
            )
        )

    async_add_entities(entities)


class CanvasCalendarEntity(CoordinatorEntity, CalendarEntity):
    _attr_attribution = "Data provided by Canvas LMS"

    def __init__(self, coordinator, hass, entry, course_id, name):
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._course_id = course_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_cal_{course_id}"
        self._attr_icon = "mdi:school"
        self._base_url = entry.data[CONF_BASE_URL].rstrip("/")
        self._token = entry.data[CONF_ACCESS_TOKEN]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": f"Canvas: {self.coordinator.data.get('name')}",
            "manufacturer": "Canvas LMS",
            "entry_type": "service",
        }

    def _get_events(self) -> list[CalendarEvent]:
        """Convert the coordinator's rolling upcoming-events cache."""
        all_data = self.coordinator.data.get("events", [])
        events = []

        for item in all_data:
            if "assignment" not in item:
                continue

            if self._course_id != "all":
                if item.get("context_code") != f"course_{self._course_id}":
                    continue

            due_at = item.get("end_at")
            if not due_at:
                continue

            start_dt = dt_util.parse_datetime(due_at)
            if not start_dt:
                continue

            points = item.get("assignment", {}).get("points_possible")
            points_str = f"\nPoints: {points}" if points is not None else ""

            events.append(
                CalendarEvent(
                    summary=item.get("title", "Assignment"),
                    start=start_dt,
                    end=start_dt,
                    description=f"Course: {item.get('context_name')}{points_str}",
                    location=item.get("html_url", ""),
                )
            )

        events.sort(key=lambda x: x.start)
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event from Canvas's rolling upcoming-events feed."""
        events = self._get_events()
        return events[0] if events else None

    def _course_ids(self):
        if self._course_id != "all":
            return [self._course_id]

        return [
            course["id"]
            for course in self.coordinator.data.get("courses", [])
            if isinstance(course, dict) and "id" in course
        ]

    def _course_name(self, course_id):
        for course in self.coordinator.data.get("courses", []):
            if str(course.get("id")) == str(course_id):
                return (
                    course.get("name")
                    or course.get("course_code")
                    or f"Course {course_id}"
                )
        return f"Course {course_id}"

    @staticmethod
    def _is_completed(assignment):
        """Return True when Canvas says the current student turned it in."""
        submission = assignment.get("submission")
        if not isinstance(submission, dict):
            return False

        workflow_state = submission.get("workflow_state")
        submitted_at = submission.get("submitted_at")

        if workflow_state in {"submitted", "graded", "pending_review"}:
            return True

        return bool(submitted_at)

    async def _request_assignment_page(self, session, url, params=None):
        headers = {"Authorization": f"Bearer {self._token}"}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=text,
                    headers=response.headers,
                )

            data = await response.json()
            next_url = None
            if response.links.get("next"):
                next_url = str(response.links["next"]["url"])
            return data, next_url

    async def _fetch_course_assignments(self, course_id, start_date, end_date):
        session = async_get_clientsession(self._hass)
        url = f"{self._base_url}/api/v1/courses/{course_id}/assignments"
        params = [
            ("include[]", "submission"),
            ("order_by", "due_at"),
            ("per_page", "100"),
        ]

        assignments = []
        first_page = True
        while url:
            page, next_url = await self._request_assignment_page(
                session, url, params if first_page else None
            )
            if isinstance(page, list):
                assignments.extend(page)
            url = next_url
            first_page = False

        range_start = dt_util.as_local(start_date)
        range_end = dt_util.as_local(end_date)
        course_name = self._course_name(course_id)
        events = []

        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue

            due_at = assignment.get("due_at")
            if not due_at:
                continue

            due_dt = dt_util.parse_datetime(due_at)
            if not due_dt:
                continue
            due_dt = dt_util.as_local(due_dt)

            if due_dt < range_start or due_dt >= range_end:
                continue

            submission = assignment.get("submission")
            workflow_state = (
                submission.get("workflow_state")
                if isinstance(submission, dict)
                else None
            )
            submitted_at = (
                submission.get("submitted_at")
                if isinstance(submission, dict)
                else None
            )
            completed = self._is_completed(assignment)

            _LOGGER.warning(
                "Canvas assignment status: course=%s assignment_id=%s name=%r "
                "workflow_state=%r submitted_at=%r completed=%s submission=%r",
                course_name,
                assignment.get("id"),
                assignment.get("name"),
                workflow_state,
                submitted_at,
                completed,
                submission,
            )

            points = assignment.get("points_possible")
            points_str = f"\nPoints: {points}" if points is not None else ""
            status_str = f"\nStatus: {workflow_state or 'unknown'}"
            submitted_str = (
                f"\nSubmitted: {submitted_at}" if submitted_at else ""
            )

            events.append(
                CalendarEvent(
                    summary=assignment.get("name", "Assignment"),
                    start=due_dt,
                    end=due_dt,
                    description=(
                        f"Course: {course_name}{points_str}{status_str}{submitted_str}"
                    ),
                    location=assignment.get("html_url", ""),
                )
            )

        return events

    async def async_get_events(
        self, hass, start_date, end_date
    ) -> list[CalendarEvent]:
        """Fetch exactly the range Home Assistant requested from Canvas."""
        results = await asyncio.gather(
            *[
                self._fetch_course_assignments(course_id, start_date, end_date)
                for course_id in self._course_ids()
            ]
        )

        events = [event for course_events in results for event in course_events]
        events.sort(key=lambda event: event.start)
        return events
