Add a ``BpmMessage`` content-rule action and matching Message portlet that
deliver a correlated BPMN message (targeting a single process instance) as
a sibling to the existing ``BpmSignal`` action/portlet (which broadcasts to
every matching waiting catch across all running instances). Use the new
portlet to fix ``renovation_demo``'s "Request extra work" trigger, which
previously broadcast a plain signal that could incorrectly also fire the
"Approve extra work" subprocess in any other concurrently-running
renovation project's Work & Extra-Work instance.
