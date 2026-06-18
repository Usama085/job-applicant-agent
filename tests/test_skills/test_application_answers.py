import pytest

from job_agent.browser.humanizer import HumanBehavior
from job_agent.database.models import Job
from job_agent.forms.detector import DetectedField
from job_agent.forms.field_mapping import FieldMapping
from job_agent.forms.filler import FormFiller
from job_agent.skills.application_answers import ApplicationAnswerBank


class FakeLocator:
    def __init__(self):
        self.value = ""

    async def click(self):
        return None

    async def fill(self, value):
        self.value = value


class FakePage:
    def __init__(self):
        self.locator_obj = FakeLocator()

    def locator(self, selector):
        return self.locator_obj


def test_answer_bank_maps_common_application_questions(sample_profile):
    answer_bank = ApplicationAnswerBank(sample_profile)

    assert answer_bank.answer_for("Are you willing to relocate?") == "Yes"
    assert answer_bank.answer_for("When can you join?") == "Immediate"
    assert answer_bank.answer_for("Do you require visa sponsorship?") == "No"


@pytest.mark.asyncio
async def test_form_filler_uses_answer_bank_for_unmapped_text_fields(sample_profile):
    filler = FormFiller(sample_profile, FieldMapping(), HumanBehavior())
    page = FakePage()
    field = DetectedField(
        selector="#question",
        field_type="textarea",
        label_text="Why should we hire you?",
    )
    job = Job(platform="linkedin", title="DevOps Engineer", company="Acme", job_url="https://example.com")

    result = await filler.fill_form(page, [field], job)

    assert result.filled_count == 1
    assert "DevOps Engineer" in page.locator_obj.value
    assert "Acme" in page.locator_obj.value
