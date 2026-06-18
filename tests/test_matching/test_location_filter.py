from job_agent.matching.location_filter import LocationFilter


def test_accepts_lahore_locations():
    location_filter = LocationFilter(["Lahore", "Lahore Pakistan", "Lahore, Pakistan"])

    assert location_filter.is_allowed("Lahore")
    assert location_filter.is_allowed("Lahore, Punjab, Pakistan")
    assert location_filter.is_allowed("Hybrid - Lahore")


def test_rejects_non_lahore_locations():
    location_filter = LocationFilter(["Lahore"])

    assert not location_filter.is_allowed("Karachi")
    assert not location_filter.is_allowed("Islamabad, Pakistan")
    assert not location_filter.is_allowed("Remote - Pakistan")


def test_missing_location_is_rejected_when_strict():
    location_filter = LocationFilter(["Lahore"], strict=True)

    assert not location_filter.is_allowed(None)
    assert not location_filter.is_allowed("")


def test_missing_location_is_allowed_when_not_strict():
    location_filter = LocationFilter(["Lahore"], strict=False)

    assert location_filter.is_allowed(None)
