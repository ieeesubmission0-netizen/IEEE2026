"""
tosca_converter.py
Module pour convertir JSON en TOSCA YAML
"""

import json
import yaml
import re


def add_all_missing_commas(json_str: str) -> str:
    """
    Aggressively fixes malformed JSON by inserting missing commas
    between JSON elements using structural heuristics.
    """
    lines = json_str.split("\n")
    fixed_lines = []

    for i in range(len(lines)):
        line = lines[i].rstrip()
        if i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if ":" in line and not line.endswith((",", "{", "[")) and (
                next_line.startswith('"')
                or next_line.startswith("{")
                or re.match(r"\d+:\{", next_line)
            ):
                line += ","
        fixed_lines.append(line)

    result = "\n".join(fixed_lines)
    result = result.replace("NULL", "null")
    result = re.sub(r"\b\d+:\{", "{", result)
    result = re.sub(r"\}\s*\{", "},\n{", result)
    result = re.sub(r'("description":"[^"]+")(\s*"nodes")', r"\1,\2", result)
    return result


def parse_json(json_text: str) -> dict:
    """Parse malformed JSON using aggressive comma repair."""
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        fixed = add_all_missing_commas(json_text)
        return json.loads(fixed)


def convert_json_to_tosca(data: dict) -> dict:
    """
    Convert JSON data (nodes with properties, capabilities, requirements)
    into a TOSCA YAML structure.
    """
    tosca = {
        "tosca_definitions_version": "tosca_simple_yaml_1_3",
        "description": data.get("description", ""),

        "node_types": {
            "computeWithblocNetwork": {
                "derived_from": "tosca.nodes.Compute",
                "requirements": [
                    {
                        "network_link": {
                            "capability": "tosca.capabilities.network.Linkable",
                            "node": "tosca.nodes.network.Network",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    },
                    {
                        "bloc_attachement": {
                            "capability": "tosca.capabilities.Attachment",
                            "node": "tosca.nodes.Storage.BlockStorage",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    },
                ],
            },
            "computeWithnetwork": {
                "derived_from": "tosca.nodes.Compute",
                "requirements": [
                    {
                        "network_link": {
                            "capability": "tosca.capabilities.network.Linkable",
                            "node": "tosca.nodes.network.Network",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    }
                ],
            },
            "computeWithblocStorage": {
                "derived_from": "tosca.nodes.Compute",
                "requirements": [
                    {
                        "bloc_attachement": {
                            "capability": "tosca.capabilities.Attachment",
                            "node": "tosca.nodes.Storage.BlockStorage",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    }
                ],
            },
            "WebAppWithDatabase": {
                "derived_from": "WebApplication",
                "requirements": [
                    {
                        "database_connection": {
                            "capability": "tosca.capabilities.Endpoint.Database",
                            "node": "Database",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    }
                ],
            },
            "WebAppWithObjStorage": {
                "derived_from": "WebApplication",
                "requirements": [
                    {
                        "object_connection": {
                            "capability": "tosca.capabilities.Endpoint",
                            "node": "tosca.nodes.Storage.ObjectStorage",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    }
                ],
            },
            "WebAppWithObjBDD": {
                "derived_from": "WebApplication",
                "requirements": [
                    {
                        "database_connection": {
                            "capability": "tosca.capabilities.Endpoint.Database",
                            "node": "Database",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    },
                    {
                        "object_connection": {
                            "capability": "tosca.capabilities.Endpoint",
                            "node": "tosca.nodes.Storage.ObjectStorage",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    },
                ],
            },

            # ---- Nouveaux node types ----
            "StorageForContainer": {
                "derived_from": "tosca.nodes.Storage.ObjectStorage",
                "capabilities": {
                    "storage": {
                        "type": "tosca.capabilities.Storage"
                    }
                }
            },
            "RuntimeForContainer": {
                "derived_from": "tosca.nodes.Container.Runtime",
                "capabilities": {
                    "host": {
                        "type": "tosca.capabilities.Compute"
                    }
                }
            },
            "NetworkForContainer": {
                "derived_from": "tosca.nodes.network.Network",
                "capabilities": {
                    "network": {
                        "type": "tosca.capabilities.Network"
                    }
                }
            },
            "ContainerWithDatabase": {
                "derived_from": "tosca.nodes.Container.Application",
                "requirements": [
                    {
                        "database_connection": {
                            "capability": "tosca.capabilities.Endpoint.Database",
                            "node": "Database",
                            "occurrences": [1, 'UNBOUNDED'],
                        }
                    }
                ]
            }
        },

        "topology_template": {"node_templates": {}},
    }

    for node in data.get("nodes", []):
        name = node.get("name")
        if not name:
            continue

        node_type = node.get("type", "")
        if node_type == "ObjectStorage":
            node_type = "tosca.nodes.Storage.ObjectStorage"
        elif node_type == "BlockStorage":
            node_type = "tosca.nodes.Storage.BlockStorage"

        node_def = {"type": node_type}

        # ---- Properties ----
        props = {}
        for prop in node.get("properties", []) or []:
            if isinstance(prop, dict) and prop.get("value") not in (None, "null"):
                props[prop.get("name")] = prop.get("value")
        if props:
            node_def["properties"] = props

        # ---- Capabilities ----
        caps = {}
        for cap in node.get("capabilities", []) or []:
            cap_name = cap.get("name")
            if not cap_name:
                continue
            cap_def = {}
            cap_props = {}
            for prop in cap.get("properties", []) or []:
                if isinstance(prop, dict) and prop.get("value") not in (None, "null"):
                    cap_props[prop.get("name")] = prop.get("value")
            if cap_props:
                cap_def["properties"] = cap_props
            caps[cap_name] = cap_def
        if caps:
            node_def["capabilities"] = caps

        # ---- Requirements ----
        reqs = []
        for req in node.get("requirements", []) or []:
            if isinstance(req, dict) and req.get("node"):
                reqs.append({req.get("name", "host"): req.get("node")})
        if reqs:
            node_def["requirements"] = reqs

        tosca["topology_template"]["node_templates"][name] = node_def

    return tosca



def generate_tosca_yaml(json_output: dict) -> str:
    """
    Convert JSON output to TOSCA YAML string.
    
    Args:
        json_output (dict): The JSON output from the agent
        
    Returns:
        str: The generated TOSCA YAML as a string
    """
    tosca = convert_json_to_tosca(json_output)
    yaml_output = yaml.dump(
        tosca,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return yaml_output