from collective.bpmproxy.behaviors.process_context import IProcessContext
from collective.bpmproxy.behaviors.process_context import IProcessContextBehavior


class IBpmProxy(IProcessContext, IProcessContextBehavior):
    """Marker interface and Dexterity Python Schema for BpmProxy

    The process configuration fields all come from IProcessContextBehavior;
    this type simply always provides the behavior's marker, so that content
    created before the behavior existed keeps working unchanged.
    """


def get_process_context(context):
    """Return the object that carries the process configuration for ``context``.

    ``Bpm Proxy`` declares the fields on its own schema, so it is its own
    process context. Behavior-enabled content is adapted. Anything else -- in
    practice the ``BpmProxy`` ProxyBase shim that wraps non-process content --
    is returned unchanged and supplies its own class-level defaults.
    """
    if IBpmProxy.providedBy(context) or not IProcessContext.providedBy(context):
        return context
    return IProcessContextBehavior(context)
