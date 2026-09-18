from collective.bpmproxy.behaviors.process_context import ProcessContextBehavior


class Content:
    """Stand-in for a behavior-enabled content object."""


def test_reads_are_delegated_to_the_content():
    content = Content()
    content.process_definition_key = "my-process"

    behavior = ProcessContextBehavior(content)

    assert behavior.process_definition_key == "my-process"


def test_schema_fields_are_written_to_the_content():
    content = Content()
    behavior = ProcessContextBehavior(content)

    behavior.diagram_enabled = True
    behavior.process_variables = {"portalUrl": "${portal_url}"}

    assert content.diagram_enabled is True
    assert content.process_variables == {"portalUrl": "${portal_url}"}


def test_non_schema_attributes_stay_on_the_adapter():
    content = Content()
    behavior = ProcessContextBehavior(content)

    behavior.some_scratch_value = "local"

    # Must not leak into content state.
    assert not hasattr(content, "some_scratch_value")
    assert behavior.some_scratch_value == "local"
