import pytest

from job_agent.browser.humanizer import HumanBehavior
from job_agent.database.models import Job
from job_agent.forms.detector import DetectedField
from job_agent.forms.field_mapping import FieldMapping
from job_agent.forms.filler import FormFillResult, FormFiller


@pytest.mark.asyncio
async def test_fill_form_reports_unknown_required_fields(sample_profile):
    filler = FormFiller(sample_profile, FieldMapping(), HumanBehavior())
    field = DetectedField(
        selector="#unknown",
        field_type="text",
        label_text="Favorite color",
        is_required=True,
    )

    result = await filler.fill_form(object(), [field])

    assert isinstance(result, FormFillResult)
    assert result.filled_count == 0
    assert result.unfilled == ["Favorite color"]
    assert result.unknown_required_count == 1


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


@pytest.mark.asyncio
async def test_fill_form_uses_generated_cover_letter_when_present(sample_profile):
    filler = FormFiller(sample_profile, FieldMapping(), HumanBehavior())
    page = FakePage()
    field = DetectedField(
        selector="#cover",
        field_type="textarea",
        label_text="Cover letter",
    )
    job = Job(platform="linkedin", title="DevOps", job_url="https://example.com")
    job.generated_cover_letter = "Generated local template text"

    result = await filler.fill_form(page, [field], job)

    assert result.filled_count == 1
    assert page.locator_obj.value == "Generated local template text"
