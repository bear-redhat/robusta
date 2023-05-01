from typing import List

from robusta.core.discovery.top_service_resolver import TopServiceResolver
from robusta.core.playbooks.base_trigger import TriggerEvent
from robusta.integrations.kubernetes.autogenerated.triggers import EventAllChangesTrigger, EventChangeEvent
from robusta.integrations.kubernetes.base_triggers import K8sTriggerEvent
from robusta.utils.rate_limiter import RateLimiter


class WarningEventTrigger(EventAllChangesTrigger):
    rate_limit: int = 3600
    operations: List[str] = None
    exclude: List[str] = None
    include: List[str] = None

    def __init__(
        self,
        name_prefix: str = None,
        namespace_prefix: str = None,
        labels_selector: str = None,
        rate_limit: int = 3600,
        operations: List[str] = None,
        exclude: List[str] = (),
        include: List[str] = (),
    ):
        super().__init__(
            name_prefix=name_prefix,
            namespace_prefix=namespace_prefix,
            labels_selector=labels_selector,
        )
        self.rate_limit = rate_limit
        self.operations = operations
        self.exclude = exclude
        self.include = include

    def should_fire(self, event: TriggerEvent, playbook_id: str):
        should_fire = super().should_fire(event, playbook_id)
        if not should_fire:
            return should_fire

        if not isinstance(event, K8sTriggerEvent):
            return False

        exec_event = self.build_execution_event(event, {})

        if not isinstance(exec_event, EventChangeEvent):
            return False

        if not exec_event.obj or not exec_event.obj.regarding:
            return False

        if exec_event.get_event().type != "Warning":
            return False

        if self.operations and exec_event.operation.value not in self.operations:
            return False

        event_content = f"{exec_event.obj.reason}{exec_event.obj.message}".lower()
        # exclude if any of the exclusions is found in the event content
        for exclusion in self.exclude:
            if exclusion.lower() in event_content:
                return False

        # exclude if all of the inclusions are NOT found in the event content
        if self.include:
            matches = [inclusion for inclusion in self.include if inclusion.lower() in event_content]
            if not matches:
                return False

        # Perform a rate limit for this service key according to the rate_limit parameter
        name = exec_event.obj.regarding.name if exec_event.obj.regarding.name else ""
        namespace = exec_event.obj.regarding.namespace if exec_event.obj.regarding.namespace else ""
        service_key = TopServiceResolver.guess_service_key(name=name, namespace=namespace)
        return RateLimiter.mark_and_test(
            f"WarningEventTrigger_{playbook_id}_{exec_event.obj.reason}",
            service_key if service_key else namespace + ":" + name,
            self.rate_limit,
        )


class WarningEventCreateTrigger(WarningEventTrigger):
    def __init__(
        self,
        name_prefix: str = None,
        namespace_prefix: str = None,
        labels_selector: str = None,
        rate_limit: int = 3600,
        exclude: List[str] = (),
        include: List[str] = (),
    ):
        super().__init__(
            name_prefix=name_prefix,
            namespace_prefix=namespace_prefix,
            labels_selector=labels_selector,
            rate_limit=rate_limit,
            operations=["create"],
            exclude=exclude,
            include=include,
        )


class WarningEventUpdateTrigger(WarningEventTrigger):
    def __init__(
        self,
        name_prefix: str = None,
        namespace_prefix: str = None,
        labels_selector: str = None,
        rate_limit: int = 3600,
        exclude: List[str] = (),
        include: List[str] = (),
    ):
        super().__init__(
            name_prefix=name_prefix,
            namespace_prefix=namespace_prefix,
            labels_selector=labels_selector,
            rate_limit=rate_limit,
            operations=["update"],
            exclude=exclude,
            include=include,
        )


class WarningEventDeleteTrigger(WarningEventTrigger):
    def __init__(
        self,
        name_prefix: str = None,
        namespace_prefix: str = None,
        labels_selector: str = None,
        rate_limit: int = 3600,
        exclude: List[str] = (),
        include: List[str] = (),
    ):
        super().__init__(
            name_prefix=name_prefix,
            namespace_prefix=namespace_prefix,
            labels_selector=labels_selector,
            rate_limit=rate_limit,
            operations=["delete"],
            exclude=exclude,
            include=include,
        )
