from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any


MSK = timezone(timedelta(hours=3))


@dataclass
class Patient:
    id: str
    full_name: str
    birth_date: date
    share_with_guardian: bool


@dataclass
class Appointment:
    id: str
    patient_id: str
    service_id: str
    branch_id: str
    slot: str
    status: str
    icd_on_referral: str | None = None


class CrmStub:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.users = {user["login"]: user for user in payload["users"]}
        self.users_by_id = {user["id"]: user for user in payload["users"]}
        self.patients = {
            row["id"]: Patient(
                id=row["id"],
                full_name=row["full_name"],
                birth_date=date.fromisoformat(row["birth_date"]),
                share_with_guardian=row["share_with_guardian"],
            )
            for row in payload["patients"]
        }
        self.links = payload["guardian_links"]
        self.appointments: list[Appointment] = [
            Appointment(**row) for row in payload["appointments"]
        ]
        self._holds: dict[str, dict[str, Any]] = {}

    def known_names(self) -> list[str]:
        """Справочник ФИО для третьего слоя обнаружения ПДн (ADR-0010)."""
        return [patient.full_name for patient in self.patients.values()]

    def actor_from_login(self, login: str):
        from app.policy.acl import Actor

        user = self.users.get(login)
        if user is None:
            return None
        return Actor(id=user["id"], login=user["login"], role=user["role"])

    def get_patient(self, patient_id: str) -> Patient | None:
        return self.patients.get(patient_id)

    def is_guardian(self, parent_id: str, child_id: str) -> bool:
        return any(
            link["parent_user_id"] == parent_id
            and link["child_patient_id"] == child_id
            and link.get("active", False)
            for link in self.links
        )

    def appointments_for(self, patient_id: str) -> list[Appointment]:
        return [item for item in self.appointments if item.patient_id == patient_id]

    def list_slots(self, service_id: str, branch_id: str, days: int = 3) -> list[str]:
        start = datetime.now(MSK).replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        slots = []
        cursor = start
        while len(slots) < days:
            if cursor.weekday() < 5:
                slots.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return slots

    def book(self, patient_id: str, service_id: str, branch_id: str, slot: str) -> Appointment:
        appointment = Appointment(
            id=f"apt-{patient_id}-{len(self.appointments) + 1}",
            patient_id=patient_id,
            service_id=service_id,
            branch_id=branch_id,
            slot=slot,
            status="planned",
        )
        self.appointments.append(appointment)
        return appointment

    def cancel(self, appointment_id: str, patient_id: str) -> bool:
        for item in self.appointments:
            if item.id == appointment_id and item.patient_id == patient_id:
                item.status = "cancelled"
                return True
        return False
