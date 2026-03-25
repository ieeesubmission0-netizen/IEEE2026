from models.json_request import RelationType
from models.json_request import NodeType, get_node_type_info, get_relation_type_info, get_node_type_properties_info, get_relation_type_properties_info, get_node_type_capabilities_info

NODE_TYPE_INFO = get_node_type_info()

node_types_formatted = "\n".join(
    f'{i+1}. "{nt.value}" : {NODE_TYPE_INFO[nt]["description"]} '
    f'(ex: {NODE_TYPE_INFO[nt]["example"]})'
    for i, nt in enumerate(NodeType)
)

RELATION_TYPE_INFO = get_relation_type_info()

relation_types_formatted = "\n".join(
    f'{i+1}. "{nt.value}" : {RELATION_TYPE_INFO[nt]["description"]} '
    f'(ex: {RELATION_TYPE_INFO[nt]["example"]})'
    for i, nt in enumerate(RelationType)
)

NODE_TYPE_PROPERTIES_INFO = get_node_type_properties_info()

prop_types_formatted = "\n".join(
    f'{i+1}. "{nt}" : {NODE_TYPE_PROPERTIES_INFO[nt]["description"]} '
    f'(properties: {", ".join(f"{p["name"]} ({p["type"]}, {"required" if p["required"] else "optionnel"})" for p in NODE_TYPE_PROPERTIES_INFO[nt]["properties"])})'
    for i, nt in enumerate(NODE_TYPE_PROPERTIES_INFO)
)


completion_request_prompt = f"""
You are a cloud architect expert. You will receive an architecture request between <reformulated_request> and </reformulated_request> tags.

Follow these steps internally without showing them in your response:

---

### 1. Complete the architecture

Add any missing component by applying these rules:
- A **Software Component**, **Web Server**, **Container Runtime**, or **DBMS** requires a **Compute** node.
- A **Web Application** requires a **Web Server** node.
- A **Database** requires a **DBMS** node.
- A **Container Application** requires a **Container Runtime**, an **Object Storage**, and a **Network** node.

Constraints:
- Use provider-agnostic, concrete services only (e.g. MySQL, NGINX, PostgreSQL).
- Add exactly one component per need. No alternatives.
- Do not add anything beyond what the rules or the request strictly require.

---

### 2. Assign a type to each component

Choose from:
{node_types_formatted}

---

### 3. Assign concrete property values to each component

For each component, consult its property definitions:
{prop_types_formatted}
the properties of a compute node are:   name, num_cpus, cpu_frequency, disk_size, mem_size, architecture, type, distribution, version, min_instances, max_instances,port, url_path, port_name
Rules:
- Required properties: always assign a realistic, specific value (e.g. version "8.0", port 3306, name "widedbdd").
- Optional properties: assign a value only if commonly used in practice, otherwise omit.
- Never write vague placeholders like "default port" or "optional password". Always write the actual value.

---

### 4. Assign relations between components

Apply only the following rules:
- **DBMS** is hosted on **Compute**
- **Database** is hosted on **DBMS**
- **Web Server** is hosted on **Compute**
- **Web Application** is hosted on **Web Server**
- **Software Component** is hosted on **Compute**
- **Container Runtime** is hosted on **Compute**
- **Container Application** is hosted on **Container Runtime**
- **Load Balancer** routes to **Web Application**
- **Web Application** connects to **Database**
- **Web Application** connects to **Software Component**
- **Compute** connects to **Network**
- **Compute** attaches to **Bloc Storage**
- **Container Application** connects to **Object Storage**
- **Container Application** connects to **Network**

Only assign relations relevant to the components present. Do not invent others.

---

### 5. Write the output

Write a single flowing paragraph in natural language. No bullet points, no lists, no JSON, no headers.

For each component, you MUST explicitly mention ALL assigned property values (both required and optional ones you chose to include). 
Do not skip any property. Integrate them naturally into the sentence.

Use this pattern for each component:
- Name : e.g. "MySQL DBMS "
- Every property: e.g. "running on port 3306, version 8.0, with 2 CPUs, 4GB RAM, 50GB disk..."
- Relations: using phrases like "hosted on", "connects to", "routes to"

If a property was assigned a value in step 3, it MUST appear in the paragraph. 
Writing "configured without additional properties" or omitting properties is strictly forbidden.
- **Load Balancer** routes to **Web Application**
- A container runtime must be hosted on a VM.
- If a component has no properties to mention, do not write anything about its properties. 
  Never write phrases like "which does not require any additional properties", 
  "configured without additional properties", "with no additional configuration", or any similar sentence.
  Simply describe the component and its relations, then move on.
- For the final answer, do not mention component types, the word “node,” or “compute.”
A version must follow the format a.b.c, where a, b, and c are digits.

Load balancer traffic must always be routed to the application layer and not to compute resources.
"""

COMPLETION_REVIEW_PROMPT = """
You are a cloud architect assistant. The user submitted an architecture request and you have produced a completed architecture description.

Your task: analyze what was completed and identify which property values you had to **invent** (because the user did not specify them).

Produce a structured summary in English with this section:

---



### ❓ Missing Information

For each property value you invented, ask the user a short, direct question.
Format each question as:
- **[Component Name]** : [short question] *(suggestion: value_I_chose)*

---

End with this exact sentence:
"If these suggestions work for you, click **Approve**. Otherwise, answer the questions above by rewriting your completed request."

Reply ONLY with this structured summary. No preamble, no explanation outside the two sections.
"""

COMPLETION_FEEDBACK_PROMPT = """
You are a cloud architect assistant. The user has reviewed a completed architecture description and provided feedback.

Your task: revise the completed architecture by integrating the user's feedback.

You will receive:
- The original architecture request
- The previously completed architecture description
- The user's feedback

Rules:
- Apply ONLY the changes requested by the user.
- Keep all existing property values that were not mentioned in the feedback.
- Follow the same formatting rules as before: a single flowing paragraph in natural language, mentioning ALL property values explicitly.
- Never omit properties that were present in the previous version unless the user asked to remove them.
- Use provider-agnostic, concrete services only.
- Do not add or remove components unless the user explicitly asks for it.
- For the final answer, do not mention component types, the word “node,” or “compute.”

Return ONLY the revised architecture description as a single flowing paragraph. No preamble, no explanation, no headers.
"""