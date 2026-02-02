#!/usr/bin/env python3
"""TrueNAS Terraform Provider Generator - Refactored for conciseness."""
import json
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"


def load_template(name):
    return (TEMPLATE_DIR / name).read_text()


TEMPLATES = {
    k: load_template(f"{k}.tmpl")
    for k in [
        "resource.go",
        "resource_update_only.go",
        "resource_with_json.go",
        "resource_vm_device.go",
        "resource_uploadable.go",
        "action_resource.go",
        "action_uploadable.go",
        "resource_doc.md",
        "datasource.go",
        "datasource_doc.md",
        "datasource_query.go",
        "datasource_query_doc.md",
    ]
}

TYPE_MAP = {
    "string": "String",
    "integer": "Int64",
    "number": "Float64",
    "boolean": "Bool",
    "array": "List",
    "object": "String",
}


def find_latest_spec():
    specs = list(Path(".").glob("truenas-methods-*.json"))
    if not specs:
        sys.exit("ERROR: No spec file found. Run: make fetch-spec")
    return sorted(specs)[-1]


def load_spec():
    spec_file = find_latest_spec()
    print(f"Using: {spec_file}", file=sys.stderr)
    with open(spec_file) as f:
        data = json.load(f)
    return data.get("methods", {}), data.get("_metadata", {})


def get_tf_type(prop):
    """Convert JSON schema to Terraform type."""
    if isinstance(prop, list):
        prop = prop[0] if prop else {}
    if not isinstance(prop, dict):
        return "String"
    if "anyOf" in prop:
        for v in prop["anyOf"]:
            if v.get("type") in ("integer", "boolean", "array"):
                return {"integer": "Int64", "boolean": "Bool", "array": "List"}[
                    v["type"]
                ]
        return "String"
    if "oneOf" in prop or "discriminator" in prop:
        return "String"
    return TYPE_MAP.get(prop.get("type"), "String")


def to_field_name(name):
    """Convert property name to Go field name."""
    if name == "CSR":
        return "Csr"
    if name == "id":
        return "ID"
    return name.title().replace("_", "")


def is_complex_object(prop):
    """Check if property needs JSON parsing."""
    if not isinstance(prop, dict):
        return False
    if prop.get("type") == "object":
        return True
    for key in ["anyOf", "oneOf"]:
        if any(v.get("type") == "object" for v in prop.get(key, [])):
            return True
    if "discriminator" in prop:
        return True
    if prop.get("type") == "array":
        items = prop.get("items", {})
        item = items[0] if isinstance(items, list) else items
        return isinstance(item, dict) and item.get("type") == "object"
    return False


def has_complex_objects(properties):
    return any(is_complex_object(p) for n, p in properties.items() if n != "provider")


def get_array_item_schema(prop):
    """Get item schema for array properties."""
    items = prop.get("items", {})
    return items[0] if isinstance(items, list) else items


def merge_anyof_schema(schema):
    """Merge anyOf variants into single schema."""
    if "anyOf" not in schema:
        return schema.get("properties", {}), schema.get("required", [])
    props = {}
    for v in schema["anyOf"]:
        props.update(v.get("properties", {}))
    all_req = [set(v.get("required", [])) for v in schema["anyOf"]]
    req = list(set.intersection(*all_req)) if all_req else []
    return props, req


# ============ Schema Generation ============


def gen_schema_attrs(properties, required, has_start=False, create_only=None):
    """Generate schema attributes."""
    create_only = create_only or set()
    lines = []

    if not has_start and not required:  # datasource
        lines.append(
            '\t\t\t"id": schema.StringAttribute{Required: true, Description: "Resource ID"},'
        )
    elif "id" not in properties:
        lines.append(
            '\t\t\t"id": schema.StringAttribute{Computed: true, Description: "Resource ID"},'
        )

    if has_start:
        lines.append(
            '\t\t\t"start_on_create": schema.BoolAttribute{Optional: true, Description: "Start the resource immediately after creation (default: true)"},'
        )

    for name, prop in properties.items():
        if name == "id":
            if not has_start and not required:
                continue
            tf_type = get_tf_type(prop)
            lines.append(
                f'\t\t\t"id": schema.{tf_type}Attribute{{Computed: true, Description: "Resource ID"}},'
            )
            continue
        if name == "provider":
            continue

        prop = prop[0] if isinstance(prop, list) else prop
        tf_type = get_tf_type(prop)
        is_req = name in required
        desc = (
            prop.get("description", "")[:100].replace('"', '\\"').replace("\n", " ")
            if isinstance(prop, dict)
            else ""
        )
        attr_name = name.lower() if name != "CSR" else "csr"

        lines.append(f'\t\t\t"{attr_name}": schema.{tf_type}Attribute{{')

        if not has_start and not required:  # datasource
            lines.append("\t\t\t\tComputed: true,")
        else:
            is_auto = (
                not is_req
                and isinstance(prop, dict)
                and "generate" in prop.get("description", "").lower()
            )
            if is_auto:
                lines.append("\t\t\t\tOptional: true,")
                lines.append("\t\t\t\tComputed: true,")
            else:
                lines.append(f"\t\t\t\tRequired: {str(is_req).lower()},")
                lines.append(f"\t\t\t\tOptional: {str(not is_req).lower()},")

        if tf_type == "List":
            lines.append("\t\t\t\tElementType: types.StringType,")
        lines.append(f'\t\t\t\tDescription: "{desc}",')

        # Plan modifiers for create-only fields
        if name in create_only and name != "name":
            mod_map = {
                "String": "stringplanmodifier",
                "Int64": "int64planmodifier",
                "Bool": "boolplanmodifier",
            }
            if tf_type in mod_map:
                lines.append(
                    f"\t\t\t\tPlanModifiers: []planmodifier.{tf_type}{{{mod_map[tf_type]}.RequiresReplace()}},"
                )

        lines.append("\t\t\t},")

    return "\n".join(lines)


def gen_fields(properties, has_start=False):
    """Generate struct fields."""
    lines = []
    is_ds = not has_start and "id" in properties

    if is_ds or "id" not in properties:
        lines.append('\tID types.String `tfsdk:"id"`')
    if has_start:
        lines.append('\tStartOnCreate types.Bool `tfsdk:"start_on_create"`')

    for name, prop in properties.items():
        if name == "provider" or (name == "id" and is_ds):
            continue
        field = to_field_name(name)
        tf_type = get_tf_type(prop)
        lines.append(f'\t{field} types.{tf_type} `tfsdk:"{name.lower()}"`')

    return "\n".join(lines)


# ============ Parameter Building ============


def gen_create_params(properties):
    """Generate parameter building code."""
    lines = []
    for name, prop in properties.items():
        if name in ("provider", "id"):
            continue
        field = to_field_name(name)
        tf_type = get_tf_type(prop)

        lines.append(f"\tif !data.{field}.IsNull() {{")

        if tf_type == "Bool":
            lines.append(f'\t\tparams["{name}"] = data.{field}.ValueBool()')
        elif tf_type == "Int64":
            lines.append(f'\t\tparams["{name}"] = data.{field}.ValueInt64()')
        elif tf_type == "Float64":
            lines.append(f'\t\tparams["{name}"] = data.{field}.ValueFloat64()')
        elif tf_type == "List":
            item = get_array_item_schema(prop) if isinstance(prop, dict) else {}
            if isinstance(item, dict) and item.get("type") == "object":
                lines.extend(
                    [
                        f"\t\tvar {name}List []string",
                        f"\t\tdata.{field}.ElementsAs(ctx, &{name}List, false)",
                        f"\t\tvar {name}Objs []map[string]interface{{}}",
                        f"\t\tfor _, jsonStr := range {name}List {{",
                        f"\t\t\tvar obj map[string]interface{{}}",
                        f"\t\t\tif err := json.Unmarshal([]byte(jsonStr), &obj); err != nil {{",
                        f'\t\t\t\tresp.Diagnostics.AddError("JSON Parse Error", fmt.Sprintf("Failed to parse {name} item: %s", err))',
                        f"\t\t\t\treturn",
                        f"\t\t\t}}",
                        f"\t\t\t{name}Objs = append({name}Objs, obj)",
                        f"\t\t}}",
                        f'\t\tparams["{name}"] = {name}Objs',
                    ]
                )
            else:
                lines.extend(
                    [
                        f"\t\tvar {name}List []string",
                        f"\t\tdata.{field}.ElementsAs(ctx, &{name}List, false)",
                        f'\t\tparams["{name}"] = {name}List',
                    ]
                )
        elif is_complex_object(prop):
            lines.extend(
                [
                    f"\t\tvar {name}Obj map[string]interface{{}}",
                    f"\t\tif err := json.Unmarshal([]byte(data.{field}.ValueString()), &{name}Obj); err != nil {{",
                    f'\t\t\tresp.Diagnostics.AddError("JSON Parse Error", fmt.Sprintf("Failed to parse {name}: %s", err))',
                    f"\t\t\treturn",
                    f"\t\t}}",
                    f'\t\tparams["{name}"] = {name}Obj',
                ]
            )
        else:
            lines.append(f'\t\tparams["{name}"] = data.{field}.ValueString()')

        lines.append("\t}")
    return "\n".join(lines)


# ============ Read Mapping ============


def gen_read_mapping(properties, skip_id=False, create_only=None, required=None):
    """Generate code to map API response to state."""
    create_only = create_only or set()
    lines = []

    # For datasources (required=None), read all fields
    # For resources (required=set), only read required fields + name/type
    def should_read_field(name):
        if name in ("provider", "id"):
            return False
        if name in create_only and name not in ("name", "type"):
            return False
        if required is not None and name not in required and name not in ("name", "type"):
            return False
        return True

    fields_to_read = [n for n in properties if should_read_field(n)]
    has_fields = not skip_id or bool(fields_to_read)

    if has_fields:
        lines.extend(
            [
                "\tresultMap, ok := result.(map[string]interface{})",
                "\tif !ok {",
                '\t\tresp.Diagnostics.AddError("Parse Error", "Failed to parse API response")',
                "\t\treturn",
                "\t}",
                "",
            ]
        )
    else:
        lines.extend(["\t_ = result // No fields to read", ""])
        return "\n".join(lines)

    if not skip_id:
        lines.extend(
            [
                '\t\tif v, ok := resultMap["id"]; ok && v != nil {',
                '\t\t\tdata.ID = types.StringValue(fmt.Sprintf("%v", v))',
                "\t\t}",
            ]
        )

    for name in fields_to_read:
        prop = properties[name]

        field = to_field_name(name)
        tf_type = get_tf_type(prop)

        lines.append(f'\t\tif v, ok := resultMap["{name}"]; ok && v != nil {{')

        if tf_type == "Bool":
            lines.append(
                f"\t\t\tif bv, ok := v.(bool); ok {{ data.{field} = types.BoolValue(bv) }}"
            )
        elif tf_type == "Int64":
            lines.extend(
                [
                    f"\t\t\tswitch val := v.(type) {{",
                    f"\t\t\tcase float64:",
                    f"\t\t\t\tdata.{field} = types.Int64Value(int64(val))",
                    f"\t\t\tcase map[string]interface{{}}:",
                    f'\t\t\t\tif parsed, ok := val["parsed"]; ok && parsed != nil {{',
                    f"\t\t\t\t\tif fv, ok := parsed.(float64); ok {{ data.{field} = types.Int64Value(int64(fv)) }}",
                    f"\t\t\t\t}}",
                    f"\t\t\t}}",
                ]
            )
        elif tf_type == "Float64":
            lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ data.{field} = types.Float64Value(fv) }}"
            )
        elif tf_type == "List":
            lines.extend(
                [
                    f"\t\t\tif arr, ok := v.([]interface{{}}); ok {{",
                    f"\t\t\t\tstrVals := make([]attr.Value, len(arr))",
                    f'\t\t\t\tfor i, item := range arr {{ strVals[i] = types.StringValue(fmt.Sprintf("%v", item)) }}',
                    f"\t\t\t\tdata.{field}, _ = types.ListValue(types.StringType, strVals)",
                    f"\t\t\t}}",
                ]
            )
        else:
            lines.extend(
                [
                    f"\t\t\tswitch val := v.(type) {{",
                    f"\t\t\tcase string:",
                    f"\t\t\t\tdata.{field} = types.StringValue(val)",
                    f"\t\t\tcase map[string]interface{{}}:",
                    f'\t\t\t\tif strVal, ok := val["value"]; ok && strVal != nil {{',
                    f'\t\t\t\t\tdata.{field} = types.StringValue(fmt.Sprintf("%v", strVal))',
                    f"\t\t\t\t}}",
                    f"\t\t\tdefault:",
                    f'\t\t\t\tdata.{field} = types.StringValue(fmt.Sprintf("%v", v))',
                    f"\t\t\t}}",
                ]
            )

        lines.append("\t\t}")

    return "\n".join(lines)


# ============ Resource Generation ============


def gen_resource(base_name, methods):
    """Generate resource file from method specs."""
    create_spec = methods.get(f"{base_name}.create", {})
    update_spec = methods.get(f"{base_name}.update", {})
    delete_spec = methods.get(f"{base_name}.delete", {})

    method_spec = create_spec or update_spec
    if not method_spec or not method_spec.get("accepts"):
        return None

    # Parse schema
    schema = (
        method_spec["accepts"][0]
        if isinstance(method_spec["accepts"], list)
        else method_spec["accepts"]
    )
    properties, required = merge_anyof_schema(schema)
    if not properties:
        return None

    # Detect ID type
    id_is_string = any(
        spec.get("accepts", [{}])[0].get("type") == "string"
        for spec in [update_spec, delete_spec]
        if spec
    )

    # Detect create-only fields
    update_props = {}
    if update_spec and len(update_spec.get("accepts", [])) >= 2:
        up_schema = update_spec["accepts"][1]
        update_props, _ = (
            merge_anyof_schema(up_schema)
            if "anyOf" in up_schema
            else (up_schema.get("properties", {}), [])
        )
        update_props = {k: v for k, v in update_props.items() if k != "id"}
    create_only = (
        set(properties.keys()) - set(update_props.keys())
        if update_props
        else set(properties.keys())
    )
    properties = {**properties, **update_props}

    # Lifecycle
    has_start = f"{base_name}.start" in methods and base_name != "app"
    has_stop = f"{base_name}.stop" in methods

    # Job flags
    create_is_job = create_spec.get("job", False)
    update_is_job = update_spec.get("job", False)
    delete_is_job = delete_spec.get("job", False)
    delete_needs_opts = len(delete_spec.get("accepts", [])) >= 2

    # Names
    resource_name = base_name.replace(".", "_").title().replace("_", "")
    tf_name = base_name.replace(".", "_")
    api_name = base_name
    desc = (
        (method_spec.get("description") or f"TrueNAS {tf_name} resource")
        .split("\n")[0][:200]
        .replace('"', '\\"')
    )

    # ID handling code
    if id_is_string:
        id_read = "\tid = data.ID.ValueString()"
        id_update = "\tid = state.ID.ValueString()"
        id_delete = (
            f"\tid = []interface{{}}{{data.ID.ValueString(), map[string]interface{{}}{{}}}}"
            if delete_needs_opts
            else "\tid = data.ID.ValueString()"
        )
    else:
        id_read = '\tid, err = strconv.Atoi(data.ID.ValueString())\n\tif err != nil {\n\t\tresp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))\n\t\treturn\n\t}'
        id_update = '\tid, err = strconv.Atoi(state.ID.ValueString())\n\tif err != nil {\n\t\tresp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))\n\t\treturn\n\t}'
        if delete_needs_opts:
            id_delete = '\tid, err = strconv.Atoi(data.ID.ValueString())\n\tif err != nil {\n\t\tresp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))\n\t\treturn\n\t}\n\tid = []interface{}{id, map[string]interface{}{}}'
        else:
            id_delete = id_read

    # Lifecycle code
    lifecycle = ""
    if has_start:
        start_call = (
            f"data.ID.ValueString()"
            if id_is_string
            else f"func() int {{ id, _ := strconv.Atoi(data.ID.ValueString()); return id }}()"
        )
        lifecycle = f"""
\tstartOnCreate := true
\tif !data.StartOnCreate.IsNull() {{ startOnCreate = data.StartOnCreate.ValueBool() }}
\tif startOnCreate {{
\t\t_, err = r.client.Call("{api_name}.start", {start_call})
\t\tif err != nil {{ resp.Diagnostics.AddWarning("Start Failed", fmt.Sprintf("Resource created but failed to start: %s", err.Error())) }}
\t}}"""

    predelete = ""
    if has_stop:
        stop_call = (
            f"data.ID.ValueString()"
            if id_is_string
            else f"func() int {{ id, _ := strconv.Atoi(data.ID.ValueString()); return id }}()"
        )
        predelete = f"""
\t_, _ = r.client.Call("{api_name}.stop", {stop_call})
\ttime.Sleep(2 * time.Second)
"""

    # Imports
    needs_strconv = (
        not id_is_string
        or (has_start and not id_is_string)
        or (has_stop and not id_is_string)
    )
    has_list = any(
        get_tf_type(p) == "List"
        and (n not in create_only or n in ("name", "type"))
        and n in required
        for n, p in properties.items()
    )
    has_json = has_complex_objects(properties)

    imports = []
    if needs_strconv:
        imports.append('"strconv"')
    if has_list and required:
        imports.append('"github.com/hashicorp/terraform-plugin-framework/attr"')
    if has_json:
        imports.append('"encoding/json"')
    if has_stop:
        imports.append('"time"')

    # Plan modifiers
    mods = {
        get_tf_type(properties[f])
        for f in create_only
        if f != "name" and f in properties
    }
    if mods & {"String", "Int64", "Bool"}:
        imports.append(
            '"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"'
        )
    for t, m in [
        ("String", "stringplanmodifier"),
        ("Int64", "int64planmodifier"),
        ("Bool", "boolplanmodifier"),
    ]:
        if t in mods:
            imports.append(
                f'"github.com/hashicorp/terraform-plugin-framework/resource/schema/{m}"'
            )

    extra_imports = "\n\t".join(imports)

    template = (
        TEMPLATES["resource_vm_device.go"]
        if api_name == "vm.device"
        else TEMPLATES["resource.go"]
    )

    return template.format(
        resource_name=resource_name,
        name=tf_name,
        api_name=api_name,
        description=desc,
        fields=gen_fields(properties, has_start),
        schema_attrs=gen_schema_attrs(properties, required, has_start, create_only),
        create_params=gen_create_params(properties),
        update_params=gen_create_params(update_props or properties),
        read_mapping=gen_read_mapping(
            properties, create_only=create_only, required=set(required)
        ),
        lifecycle_code=lifecycle,
        predelete_code=predelete,
        id_read_code=id_read,
        id_update_code=id_update,
        id_delete_code=id_delete,
        extra_imports=extra_imports,
        create_call="CallWithJob" if create_is_job else "Call",
        update_call="CallWithJob" if update_is_job else "Call",
        delete_call="CallWithJob" if delete_is_job else "Call",
    )


# ============ Action Resource Generation ============


def gen_action_resource(method_name, method_spec):
    """Generate action resource."""
    parts = method_name.split(".")
    if len(parts) < 2:
        return None

    accepts = method_spec.get("accepts", [])
    if not accepts:
        return None

    properties = {p.get("_name_", ""): p for p in accepts if p.get("_name_")}
    if not properties:
        return None

    resource_name = "Action" + "".join(p.title() for p in parts)
    resource_type = f"action_{method_name.replace('.', '_')}"
    desc = (
        (method_spec.get("description") or f"Execute {method_name}")
        .replace("\n", " ")
        .replace('"', '\\"')[:200]
        .strip()
    )

    # Fields
    fields = "\n".join(
        f'\t{"".join(p.title() for p in n.split("_"))} types.{get_tf_type(p) if get_tf_type(p) not in ("List", "Object") else "String"} `tfsdk:"{n}"`'
        for n, p in properties.items()
    )

    # Schema
    schema_lines = []
    for n, p in properties.items():
        tf_type = (
            get_tf_type(p) if get_tf_type(p) not in ("List", "Object") else "String"
        )
        req = p.get("_required_", False)
        d = p.get("description", "").replace('"', '\\"').replace("\n", " ")[:200]
        req_opt = "Required" if req else "Optional"
        schema_lines.append(
            f'\t\t\t"{n}": schema.{tf_type}Attribute{{{req_opt}: true, MarkdownDescription: "{d}"}},'
        )

    # Params
    param_lines = ["\tparams := []interface{}{}"]
    needs_json = False
    for n, p in properties.items():
        field = "".join(part.title() for part in n.split("_"))
        tf_type = get_tf_type(p)
        req = p.get("_required_", False)

        if tf_type in ("List", "Object"):
            needs_json = True
            if req:
                param_lines.extend(
                    [
                        f"\tvar {n}Val interface{{}}",
                        f"\tif err := json.Unmarshal([]byte(data.{field}.ValueString()), &{n}Val); err == nil {{ params = append(params, {n}Val) }}",
                    ]
                )
            else:
                param_lines.extend(
                    [
                        f"\tif !data.{field}.IsNull() {{",
                        f"\t\tvar {n}Val interface{{}}",
                        f"\t\tif err := json.Unmarshal([]byte(data.{field}.ValueString()), &{n}Val); err == nil {{ params = append(params, {n}Val) }}",
                        "\t}",
                    ]
                )
        else:
            val_method = {
                "String": "ValueString",
                "Int64": "ValueInt64",
                "Bool": "ValueBool",
                "Float64": "ValueFloat64",
            }.get(tf_type, "ValueString")
            if req:
                param_lines.append(
                    f"\tparams = append(params, data.{field}.{val_method}())"
                )
            else:
                param_lines.extend(
                    [
                        f"\tif !data.{field}.IsNull() {{ params = append(params, data.{field}.{val_method}()) }}",
                    ]
                )

    code = TEMPLATES["action_resource.go"]
    for k, v in {
        "{resource_name}": resource_name,
        "{resource_type_name}": resource_type,
        "{fields}": fields,
        "{schema_attrs}": "\n".join(schema_lines),
        "{param_building}": "\n".join(param_lines),
        "{method_name}": method_name,
        "{description}": desc,
        "{is_job}": "true" if method_spec.get("job") else "false",
        "{extra_imports}": '\n\t"encoding/json"' if needs_json else "",
    }.items():
        code = code.replace(k, v)
    return code


# ============ Uploadable Resource Generation ============


def gen_uploadable_resource(method_name, method_spec, is_action=False):
    """Generate uploadable resource or action."""
    parts = method_name.split(".")
    if len(parts) < 2:
        return None

    template = (
        TEMPLATES["action_uploadable.go"]
        if is_action
        else TEMPLATES["resource_uploadable.go"]
    )

    if is_action:
        resource_name = "Action" + "".join(p.title() for p in parts)
        resource_type = f"action_{method_name.replace('.', '_')}"
    else:
        resource_name = "".join(p.title() for p in parts)
        resource_type = method_name.replace(".", "_")

    endpoint = method_name.replace(".", "/")
    desc = (
        (
            method_spec.get("description")
            or f"{'Execute' if is_action else 'Upload via'} {method_name}"
        )
        .replace("\n", " ")
        .replace('"', '\\"')[:200]
        .strip()
    )

    accepts = method_spec.get("accepts", [])
    properties = {}
    for p in accepts:
        name = p.get("_name_", "")
        if name == "id":
            name = "dataset_id"
        if name:
            properties[name] = p

    # Fields
    fields = "\n".join(
        f'\t{"".join(p.title() for p in n.split("_"))} types.{get_tf_type(p) if get_tf_type(p) not in ("List", "Object") else "String"} `tfsdk:"{n}"`'
        for n, p in properties.items()
    )

    # Schema
    schema_lines = []
    for n, p in properties.items():
        tf_type = (
            get_tf_type(p) if get_tf_type(p) not in ("List", "Object") else "String"
        )
        req = p.get("_required_", False)
        d = p.get("description", "").replace('"', '\\"').replace("\n", " ")[:200]
        req_opt = "Required" if req else "Optional"
        schema_lines.append(
            f'\t\t\t"{n}": schema.{tf_type}Attribute{{{req_opt}: true, MarkdownDescription: "{d}"}},'
        )

    # Params
    param_lines = ["\tparams := make(map[string]interface{})"]
    needs_json = False
    for n, p in properties.items():
        field = "".join(part.title() for part in n.split("_"))
        tf_type = get_tf_type(p)
        req = p.get("_required_", False)
        api_name = "id" if n == "dataset_id" else n

        if tf_type in ("List", "Object"):
            needs_json = True
            if req:
                param_lines.extend(
                    [
                        f"\tvar {n}Val interface{{}}",
                        f'\tif err := json.Unmarshal([]byte(data.{field}.ValueString()), &{n}Val); err == nil {{ params["{api_name}"] = {n}Val }}',
                    ]
                )
            else:
                param_lines.extend(
                    [
                        f"\tif !data.{field}.IsNull() {{",
                        f"\t\tvar {n}Val interface{{}}",
                        f'\t\tif err := json.Unmarshal([]byte(data.{field}.ValueString()), &{n}Val); err == nil {{ params["{api_name}"] = {n}Val }}',
                        "\t}",
                    ]
                )
        else:
            val_method = {
                "String": "ValueString",
                "Int64": "ValueInt64",
                "Bool": "ValueBool",
                "Float64": "ValueFloat64",
            }.get(tf_type, "ValueString")
            if req:
                param_lines.append(
                    f'\tparams["{api_name}"] = data.{field}.{val_method}()'
                )
            else:
                param_lines.append(
                    f'\tif !data.{field}.IsNull() {{ params["{api_name}"] = data.{field}.{val_method}() }}'
                )

    # ID generation
    if properties:
        first_name = list(properties.keys())[0]
        first_field = "".join(p.title() for p in first_name.split("_"))
        first_type = get_tf_type(properties[first_name])
        if first_type == "String":
            id_gen = f"\tdata.ID = data.{first_field}"
        elif first_type == "Int64":
            id_gen = f'\tdata.ID = types.StringValue(fmt.Sprintf("%d", data.{first_field}.ValueInt64()))'
        else:
            id_gen = f"\tdata.ID = types.StringValue(data.{first_field}.String())"
    else:
        id_gen = f'\tdata.ID = types.StringValue("{method_name}")'

    for k, v in {
        "{resource_name}": resource_name,
        "{resource_type_name}": resource_type,
        "{fields}": fields,
        "{schema_attrs}": "\n".join(schema_lines),
        "{param_building}": "\n".join(param_lines),
        "{method_name}": method_name,
        "{endpoint_path}": endpoint,
        "{description}": desc,
        "{is_job}": "true" if method_spec.get("job") else "false",
        "{id_generation}": id_gen,
        "{extra_imports}": '\n\t"encoding/json"' if needs_json else "",
    }.items():
        template = template.replace(k, v)
    return template


# ============ Data Source Generation ============


def gen_datasource(base_name, methods):
    """Generate data source."""
    get_spec = methods.get(f"{base_name}.get_instance", {})
    returns = get_spec.get("returns", [])
    if not returns:
        return None

    schema = returns[0] if isinstance(returns, list) else returns
    properties = schema.get("properties", {})
    if not properties:
        return None

    resource_name = base_name.replace(".", "_").title().replace("_", "")
    tf_name = base_name.replace(".", "_")
    desc = (
        (get_spec.get("description") or f"Retrieves TrueNAS {tf_name} data")
        .split("\n")[0][:200]
        .replace('"', '\\"')
    )

    id_type = get_tf_type(properties.get("id", {"type": "string"}))
    if id_type == "Int64":
        id_param = (
            "func() int { id, _ := strconv.Atoi(data.ID.ValueString()); return id }()"
        )
        extra_imports = '\n\t"strconv"'
    else:
        id_param = "data.ID.ValueString()"
        extra_imports = ""

    # Add attr import if any List fields exist
    if any(get_tf_type(p) == "List" for p in properties.values()):
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/attr"'

    return TEMPLATES["datasource.go"].format(
        resource_name=resource_name,
        name=tf_name,
        api_name=base_name,
        description=desc,
        fields=gen_fields(properties, False),
        schema_attrs=gen_schema_attrs(properties, [], False),
        read_mapping=gen_read_mapping(properties, skip_id=True),
        extra_imports=extra_imports,
        id_param=id_param,
    )


def gen_query_datasource(base_name, methods):
    """Generate query data source."""
    query_spec = methods.get(f"{base_name}.query", {})
    returns = query_spec.get("returns", [])
    if not returns:
        return None

    schema = returns[0] if isinstance(returns, list) else returns
    if "anyOf" in schema:
        for v in schema["anyOf"]:
            if v.get("type") == "array":
                schema = v
                break
    if schema.get("type") != "array":
        return None

    items = schema.get("items", {})
    items = items[0] if isinstance(items, list) else items
    properties = {
        k: v for k, v in items.get("properties", {}).items() if get_tf_type(v) != "List"
    }
    if not properties:
        return None

    resource_name = base_name.replace(".", "_").title().replace("_", "") + "s"
    tf_name = base_name.replace(".", "_") + "s"
    desc = (
        (query_spec.get("description") or f"Query {tf_name}")
        .split("\n")[0][:200]
        .replace('"', '\\"')
    )

    # Read mapping for items
    read_lines = []
    for n, p in properties.items():
        if n == "provider":
            continue
        field = to_field_name(n)
        tf_type = get_tf_type(p)
        read_lines.append(f'\t\tif v, ok := resultMap["{n}"]; ok && v != nil {{')
        if tf_type == "Bool":
            read_lines.append(
                f"\t\t\tif bv, ok := v.(bool); ok {{ itemModel.{field} = types.BoolValue(bv) }}"
            )
        elif tf_type == "Int64" and n != "id":
            read_lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ itemModel.{field} = types.Int64Value(int64(fv)) }}"
            )
        elif tf_type == "Float64":
            read_lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ itemModel.{field} = types.Float64Value(fv) }}"
            )
        else:
            read_lines.append(
                f'\t\t\titemModel.{field} = types.StringValue(fmt.Sprintf("%v", v))'
            )
        read_lines.append("\t\t}")

    # Attr types
    attr_lines = []
    for n, p in sorted(properties.items()):
        if n == "provider":
            continue
        tf_type = "String" if n == "id" else get_tf_type(p)
        if tf_type == "List":
            continue
        attr_name = n.lower() if n != "CSR" else "csr"
        type_map = {
            "String": "StringType",
            "Int64": "Int64Type",
            "Bool": "BoolType",
            "Float64": "Float64Type",
        }
        if tf_type in type_map:
            attr_lines.append(f'\t\t\t"{attr_name}": types.{type_map[tf_type]},')

    return TEMPLATES["datasource_query.go"].format(
        resource_name=resource_name,
        name=tf_name,
        api_name=base_name,
        description=desc,
        fields=gen_fields(properties, False),
        schema_attrs=gen_schema_attrs(properties, [], False),
        read_mapping="\n".join(read_lines),
        attr_types="\n".join(attr_lines),
    )


# ============ Documentation Generation ============


def gen_resource_docs(
    base_name, properties, required, description, methods, anyof_variants=None
):
    """Generate resource documentation."""
    tf_name = base_name.replace(".", "_")
    has_start = f"{base_name}.start" in methods

    # Example
    example_lines = []
    for n in sorted(required):
        if n in properties and n not in ("uuid", "id"):
            tf_type = get_tf_type(properties[n])
            val = {
                "String": '"example"',
                "Int64": "1",
                "Bool": "true",
                "Float64": "1.0",
                "List": '["item"]',
            }.get(tf_type, '"value"')
            example_lines.append(f"  {n} = {val}")
    if has_start and len(example_lines) < 8:
        example_lines.append("  start_on_create = true")

    # Args
    req_args, opt_args = [], []
    if has_start:
        opt_args.append(
            "- `start_on_create` (Bool) - Start immediately after creation. Default: `true`"
        )

    # Collect all enum values for discriminator field from anyOf variants
    all_enum_values = {}
    if anyof_variants:
        for fn in ["type", "kind", "variant"]:
            values = []
            for variant in anyof_variants:
                v_props = variant.get("properties", {})
                if fn in v_props:
                    dp = v_props[fn]
                    if isinstance(dp, dict) and "enum" in dp:
                        values.extend(dp["enum"])
            if values:
                all_enum_values[fn] = list(dict.fromkeys(values))  # dedupe preserving order

    for n, p in sorted(properties.items()):
        if n in ("provider", "uuid", "id"):
            continue
        tf_type = get_tf_type(p)
        desc = (
            p.get("description", "").replace("\n", " ")[:200]
            if isinstance(p, dict)
            else ""
        )
        # Add JSON object hint with example for complex types
        if tf_type == "String" and isinstance(p, dict) and is_complex_object(p):
            desc += " **Note:** This is a JSON object. Use `jsonencode()` to pass structured data."
            # Try to show object structure - check multiple locations
            obj_props = None
            if "properties" in p:
                obj_props = p["properties"]
            elif "anyOf" in p:
                for v in p["anyOf"]:
                    if isinstance(v, dict) and "properties" in v:
                        obj_props = v["properties"]
                        break
            elif "oneOf" in p:
                for v in p["oneOf"]:
                    if isinstance(v, dict) and "properties" in v:
                        obj_props = v["properties"]
                        break
            if obj_props:
                examples = []
                for pn, pv in list(obj_props.items())[:3]:
                    pt = pv.get("type", "string") if isinstance(pv, dict) else "string"
                    if pt == "string": examples.append(f'{pn} = "value"')
                    elif pt == "integer": examples.append(f"{pn} = 0")
                    elif pt == "boolean": examples.append(f"{pn} = true")
                if examples:
                    more = ", ..." if len(obj_props) > 3 else ""
                    desc += f" Example: `jsonencode({{{', '.join(examples)}{more}}})`"
        if isinstance(p, dict) and "default" in p:
            desc += f" Default: `{p['default']}`"
        # Use collected enum values for discriminator fields in anyOf schemas
        if n in all_enum_values:
            desc += f" Valid values: {', '.join(f'`{v}`' for v in all_enum_values[n][:10])}"
        elif isinstance(p, dict) and "enum" in p:
            desc += f" Valid values: {', '.join(f'`{v}`' for v in p['enum'][:10])}"
        line = f"- `{n}` ({tf_type}) - {desc}"
        (req_args if n in required else opt_args).append(line)

    generic_example = (
        f"""
## Example Usage

```terraform
resource "truenas_{tf_name}" "example" {{
{chr(10).join(example_lines) or "  # Configure required attributes"}
}}
```
"""
        if not anyof_variants
        else ""
    )

    # Build variant examples for anyOf schemas
    variant_examples = ""
    if anyof_variants:
        # Find discriminator field
        disc_field = None
        for fn in ["type", "kind", "variant"]:
            if fn in properties and isinstance(properties[fn], dict) and "enum" in properties[fn]:
                disc_field = fn
                break
        
        if disc_field:
            variant_examples = f"\n## Variants\n\nThis resource has **{len(anyof_variants)} variants** controlled by the `{disc_field}` field.\n\n"
            
            for variant in anyof_variants:
                v_props = variant.get("properties", {})
                v_req = set(variant.get("required", []))
                
                # Get variant name from discriminator
                v_name = None
                if disc_field in v_props:
                    dp = v_props[disc_field]
                    if isinstance(dp, dict):
                        if "enum" in dp and dp["enum"]:
                            v_name = dp["enum"][0]
                        elif "default" in dp:
                            v_name = dp["default"]
                
                if v_name:
                    variant_examples += f"### {v_name}\n\n```terraform\n"
                    variant_examples += f'resource "truenas_{tf_name}" "example" {{\n'
                    variant_examples += f'  {disc_field} = "{v_name}"\n'
                    for rn in sorted(v_req):
                        if rn != disc_field and rn in properties:
                            variant_examples += f'  {rn} = "value"\n'
                    variant_examples += "}\n```\n\n"
                    variant_examples += f"**Required fields:** {', '.join(f'`{r}`' for r in sorted(v_req))}\n\n"

    doc = TEMPLATES["resource_doc.md"].format(
        resource_type=tf_name,
        description=description,
        required_args=chr(10).join(req_args) or "- None",
        optional_args=chr(10).join(opt_args) or "- None",
        variant_examples=variant_examples,
        generic_example=generic_example,
    )

    Path("docs/resources").mkdir(parents=True, exist_ok=True)
    Path(f"docs/resources/{tf_name}.md").write_text(doc)


def gen_datasource_docs(base_name, properties, description):
    """Generate data source documentation."""
    tf_name = base_name.replace(".", "_")
    attrs = [
        f"- `{n}` ({get_tf_type(p)}) - {p.get('description', '')[:200].replace(chr(10), ' ').strip()}"
        for n, p in sorted(properties.items())
        if n != "id" and isinstance(p, dict)
    ]

    doc = TEMPLATES["datasource_doc.md"].format(
        resource_type=tf_name,
        description=description,
        name=tf_name,
        attrs=chr(10).join(attrs) or "- None",
    )
    Path("docs/data-sources").mkdir(parents=True, exist_ok=True)
    Path(f"docs/data-sources/{tf_name}.md").write_text(doc)


def gen_action_docs(method_name, properties, description):
    """Generate action documentation."""
    resource_name = f"action_{method_name.replace('.', '_')}"

    example = f'resource "truenas_{resource_name}" "example" {{\n'
    for n, p in properties.items():
        if p.get("_required_"):
            tf_type = get_tf_type(p)
            val = {"String": '"value"', "Int64": "1", "Bool": "true"}.get(
                tf_type, '"value"'
            )
            example += f"  {n} = {val}\n"
    example += "}"

    schema_lines = []
    for n, p in properties.items():
        tf_type = get_tf_type(p)
        req = "Required" if p.get("_required_") else "Optional"
        desc = p.get("description", "").replace("\n", " ")[:200]
        schema_lines.append(f"- `{n}` ({tf_type}, {req}) {desc}")

    doc = f"""---
page_title: "truenas_{resource_name} Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  {description}
---

# truenas_{resource_name} (Resource)

{description}

This is an action resource that executes the `{method_name}` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
{example}
```

## Schema

### Input Parameters

{chr(10).join(schema_lines) or "None"}

### Computed Outputs

- `action_id` (String) Unique identifier for this action execution
- `job_id` (Int64) Background job ID (if applicable)
- `state` (String) Job state: SUCCESS, FAILED, or RUNNING
- `progress` (Float64) Job progress percentage (0-100)
- `result` (String) Action result data
- `error` (String) Error message if action failed

## Notes

- Actions execute immediately when the resource is created
- Background jobs are monitored until completion
- Progress updates are logged during execution
- The resource cannot be updated - changes force recreation
- Destroying the resource does not undo the action
"""
    Path("docs/resources").mkdir(parents=True, exist_ok=True)
    Path(f"docs/resources/{resource_name}.md").write_text(doc)


# ============ Provider Generation ============


def gen_provider(resources, datasources, actions, uploadables):
    """Generate provider.go."""
    with open("templates/provider.go.tmpl") as f:
        template = f.read()

    resource_funcs = [
        f"New{r.replace('.', '_').title().replace('_', '')}Resource" for r in resources
    ]
    uploadable_funcs = [
        f"New{''.join(p.title() for p in u.split('.'))}Resource" for u in uploadables
    ]
    action_funcs = [
        f"NewAction{''.join(p.title() for p in a.split('.'))}Resource" for a in actions
    ]

    all_funcs = resource_funcs + uploadable_funcs + action_funcs
    ds_funcs = [
        f"New{d.replace('.', '_').title().replace('_', '')}DataSource"
        for d in datasources
    ]

    code = template.replace("{{resource_list}}", ",\n\t\t".join(all_funcs))
    code = code.replace(
        "{{datasource_list}}", ",\n\t\t".join(ds_funcs) + ("," if ds_funcs else "")
    )

    Path("internal/provider/provider.go").write_text(code)
    print("✅ Generated provider.go", file=sys.stderr)


# ============ Main ============


def main():
    print("=" * 60, file=sys.stderr)
    print("TrueNAS Provider Generator", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    methods, metadata = load_spec()
    print(f"Version: {metadata.get('truenas_version')}", file=sys.stderr)
    print(f"Methods: {len(methods)}", file=sys.stderr)

    output_dir = Path("internal/provider")
    skip = {"nvmet.port"}

    # Resources
    resources = [m[:-7] for m in methods if m.endswith(".create")]
    generated_resources = []
    for base in resources:
        if base in skip:
            continue
        code = gen_resource(base, methods)
        if code:
            (output_dir / f"resource_{base.replace('.', '_')}_generated.go").write_text(
                code
            )
            generated_resources.append(base)

            # Docs
            spec = methods.get(f"{base}.create", {})
            if spec.get("accepts"):
                schema = (
                    spec["accepts"][0]
                    if isinstance(spec["accepts"], list)
                    else spec["accepts"]
                )
                props, req = merge_anyof_schema(schema)
                desc = (spec.get("description") or f"Manages {base}").split("\n")[0][
                    :200
                ]
                gen_resource_docs(base, props, req, desc, methods, schema.get("anyOf"))

    print(f"✅ Generated {len(generated_resources)} resources", file=sys.stderr)

    # Actions
    action_keywords = [
        "start",
        "stop",
        "restart",
        "run",
        "sync",
        "scrub",
        "backup",
        "restore",
        "rollback",
        "redeploy",
    ]
    uploadable_actions = {"mail.send", "support.attach_ticket"}
    skip_uploadable = {"pool.dataset.encryption_summary"}

    generated_actions, generated_uploadables = [], []

    for method, spec in methods.items():
        if any(
            method.endswith(s)
            for s in [".create", ".update", ".delete", ".query", ".get_instance"]
        ):
            continue

        is_uploadable = spec.get("uploadable", False)

        if is_uploadable:
            if method in skip_uploadable:
                continue
            if method in uploadable_actions:
                code = gen_uploadable_resource(method, spec, is_action=True)
                if code:
                    (
                        output_dir / f"action_{method.replace('.', '_')}_generated.go"
                    ).write_text(code)
                    generated_actions.append(method)
            else:
                code = gen_uploadable_resource(method, spec, is_action=False)
                if code:
                    (
                        output_dir / f"resource_{method.replace('.', '_')}_generated.go"
                    ).write_text(code)
                    generated_uploadables.append(method)
            continue

        if spec.get("job") or any(k in method.split(".")[-1] for k in action_keywords):
            code = gen_action_resource(method, spec)
            if code:
                (
                    output_dir / f"action_{method.replace('.', '_')}_generated.go"
                ).write_text(code)
                generated_actions.append(method)

                props = {
                    p.get("_name_", ""): p
                    for p in spec.get("accepts", [])
                    if p.get("_name_")
                }
                desc = (spec.get("description") or f"Execute {method}").replace("\n", " ").strip()
                gen_action_docs(method, props, desc)

    print(
        f"✅ Generated {len(generated_actions)} actions, {len(generated_uploadables)} uploadables",
        file=sys.stderr,
    )

    # Data sources
    ds_candidates = [
        "vm",
        "pool",
        "pool.dataset",
        "disk",
        "user",
        "group",
        "interface",
        "service",
    ]
    generated_ds, generated_query = [], []

    for base in ds_candidates:
        if f"{base}.get_instance" in methods:
            code = gen_datasource(base, methods)
            if code:
                (
                    output_dir / f"datasource_{base.replace('.', '_')}_generated.go"
                ).write_text(code)
                generated_ds.append(base)

                spec = methods[f"{base}.get_instance"]
                returns = spec.get("returns", [])
                if returns:
                    schema = returns[0] if isinstance(returns, list) else returns
                    gen_datasource_docs(
                        base,
                        schema.get("properties", {}),
                        (spec.get("description") or f"Get {base}").split("\n")[0][:200],
                    )

        if f"{base}.query" in methods:
            code = gen_query_datasource(base, methods)
            if code:
                (
                    output_dir / f"datasource_{base.replace('.', '_')}s_generated.go"
                ).write_text(code)
                generated_query.append(base + "s")

    print(
        f"✅ Generated {len(generated_ds)} datasources, {len(generated_query)} query datasources",
        file=sys.stderr,
    )

    gen_provider(
        generated_resources,
        generated_ds + generated_query,
        generated_actions,
        generated_uploadables,
    )


if __name__ == "__main__":
    main()
