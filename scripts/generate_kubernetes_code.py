import argparse
import os
import textwrap
import inflection
from typing import TextIO

KUBERNETES_VERSIONS = ["v1", "v2beta1", "v2beta2"]
KUBERNETES_RESOURCES = ["Pod", "ReplicaSet", "DaemonSet", "Deployment", "Service", "ConfigMap", "Event", "HorizontalPodAutoscaler", "Node"]
TRIGGER_TYPES = {
    "create": "K8sOperationType.CREATE",
    "update": "K8sOperationType.UPDATE",
    "delete": "K8sOperationType.DELETE",
    "all_changes": "None",
}

CUSTOM_SUBCLASSES = {
    "Pod": "RobustaPod",
    "Deployment": "RobustaDeployment"
}
CUSTOM_SUBCLASSES_NAMES_STR = ",".join(CUSTOM_SUBCLASSES.values())

COMMON_PREFIX = """# This file was autogenerated. Do not edit.\n\n"""


def get_model_class(k8s_resource_name: str) -> str:
    if k8s_resource_name in CUSTOM_SUBCLASSES:
        return CUSTOM_SUBCLASSES[k8s_resource_name]
    return k8s_resource_name


def autogenerate_events(f: TextIO):
    f.write(COMMON_PREFIX)
    f.write(textwrap.dedent(f"""\
        from dataclasses import dataclass
        from typing import Union
        from ..base_event import K8sBaseEvent
        from ..custom_models import {CUSTOM_SUBCLASSES_NAMES_STR}
        """))

    for version in KUBERNETES_VERSIONS:
        for resource in KUBERNETES_RESOURCES:
            f.write(textwrap.dedent(f"""\
                from hikaru.model.rel_1_16.{version} import {resource} as {version}{resource}    
                """))


    all_versioned_resources = set()
    for resource in KUBERNETES_RESOURCES:
        if resource in CUSTOM_SUBCLASSES:
            model_class_str = get_model_class(resource)
            all_versioned_resources.add(model_class_str)
        else:
            version_resources = [f"{version}{resource}" for version in KUBERNETES_VERSIONS]
            model_class_str = f"Union[{','.join(version_resources)}]"
            all_versioned_resources = all_versioned_resources.union(set(version_resources))

        f.write(textwrap.dedent(f"""\
        
            @dataclass
            class {resource}Event (K8sBaseEvent):
                obj: {model_class_str}
                old_obj: {model_class_str}
            
            """))

    # add the KubernetesAnyEvent
    f.write(textwrap.dedent(f"""\

        @dataclass
        class KubernetesAnyEvent (K8sBaseEvent):
            obj: {f"Union[{','.join(all_versioned_resources)}]"}
            old_obj: {f"Union[{','.join(all_versioned_resources)}]"}

        """))

    mappers = [f"'{r}': {r}Event" for r in KUBERNETES_RESOURCES]
    mappers_str = ",\n    ".join(mappers)
    f.write(f"\nKIND_TO_EVENT_CLASS = {{\n    {mappers_str}\n}}\n")


def autogenerate_models(f: TextIO, version : str):
    f.write(COMMON_PREFIX)
    f.write(textwrap.dedent(f"""\
        from hikaru.model.rel_1_16.{version} import *
        from ...custom_models import {CUSTOM_SUBCLASSES_NAMES_STR}


        """))

    mappers = [f"'{r}': {get_model_class(r)}" for r in KUBERNETES_RESOURCES]
    mappers_str = ",\n    ".join(mappers)
    f.write(f"KIND_TO_MODEL_CLASS = {{\n    {mappers_str}\n}}\n")


def autogenerate_versioned_models(f: TextIO):
    f.write(COMMON_PREFIX)
    for version in KUBERNETES_VERSIONS:

        f.write(textwrap.dedent(f"""\
            from .{version}.models import KIND_TO_MODEL_CLASS as {version}
            """))

    mappers = [f"'{version}': {version}" for version in KUBERNETES_VERSIONS]
    mappers_str = ",\n    ".join(mappers)

    f.write(f"VERSION_KIND_TO_MODEL_CLASS = {{\n    {mappers_str}\n}}\n")
    f.write(textwrap.dedent(f"""\


        def get_api_version(apiVersion: str):
            if "/" in apiVersion:
                apiVersion = apiVersion.split("/")[1]
            return VERSION_KIND_TO_MODEL_CLASS.get(apiVersion)
        """))



def autogenerate_triggers(f: TextIO):
    f.write(COMMON_PREFIX)
    f.write(textwrap.dedent("""\
        from ....utils.decorators import doublewrap
        from ..base_triggers import register_k8s_playbook, register_k8s_any_playbook
        from ..base_event import K8sOperationType
        
        
        """))

    for resource in KUBERNETES_RESOURCES:
        f.write(f"# {resource} Triggers\n")
        for trigger_name, operation_type in TRIGGER_TYPES.items():
            f.write(textwrap.dedent(f"""\
            @doublewrap
            def on_{resource.lower()}_{trigger_name}(func, name_prefix='', namespace_prefix=''):
                return register_k8s_playbook(func, '{resource}', {operation_type}, name_prefix=name_prefix, namespace_prefix=namespace_prefix)
            
            
            """))

    f.write(f"# Kubernetes Any Triggers\n")
    for trigger_name, operation_type in TRIGGER_TYPES.items():
        f.write(textwrap.dedent(f"""\
        @doublewrap
        def on_kubernetes_any_resource_{trigger_name}(func, name_prefix='', namespace_prefix=''):
            return register_k8s_any_playbook(func, {operation_type}, name_prefix=name_prefix, namespace_prefix=namespace_prefix)


        """))


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    output_dir = os.path.join(root_dir, "src/robusta/integrations/kubernetes/autogenerated/")

    parser = argparse.ArgumentParser(description='Autogenerate kubernetes models, events, and triggers')
    parser.add_argument('-o', '--output', default=output_dir, type=str, help='output directory')
    args = parser.parse_args()

    # generate versioned events and models
    for version in KUBERNETES_VERSIONS:
        dir_path = os.path.join(args.output, version)
        os.makedirs(dir_path, exist_ok=True)
        with open(os.path.join(dir_path, "models.py"), "w") as f:
            autogenerate_models(f, version)

    # generate all version unions
    with open(os.path.join(args.output, "events.py"), "w") as f:
        autogenerate_events(f)
    with open(os.path.join(args.output, "models.py"), "w") as f:
        autogenerate_versioned_models(f)
    with open(os.path.join(args.output, "triggers.py"), "w") as f:
        autogenerate_triggers(f)


if __name__ == "__main__":
    main()
