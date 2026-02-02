#!/usr/bin/env python3
"""
Generate Terraform provider from TrueNAS native method specifications.
Replaces OpenAPI-based generator with native core.get_methods approach.
"""
import copy
import json
import sys
from pathlib import Path

# Load templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
RESOURCE_TEMPLATE = (TEMPLATE_DIR / "resource.go.tmpl").read_text()
RESOURCE_UPDATE_ONLY_TEMPLATE = (
    TEMPLATE_DIR / "resource_update_only.go.tmpl"
).read_text()
RESOURCE_WITH_JSON_TEMPLATE = (TEMPLATE_DIR / "resource_with_json.go.tmpl").read_text()
RESOURCE_VM_DEVICE_TEMPLATE = (TEMPLATE_DIR / "resource_vm_device.go.tmpl").read_text()
ACTION_RESOURCE_TEMPLATE = (TEMPLATE_DIR / "action_resource.go.tmpl").read_text()
RESOURCE_DOC_TEMPLATE = (TEMPLATE_DIR / "resource_doc.md.tmpl").read_text()
DATASOURCE_TEMPLATE = (TEMPLATE_DIR / "datasource.go.tmpl").read_text()
DATASOURCE_DOC_TEMPLATE = (TEMPLATE_DIR / "datasource_doc.md.tmpl").read_text()
DATASOURCE_QUERY_TEMPLATE = (TEMPLATE_DIR / "datasource_query.go.tmpl").read_text()
DATASOURCE_QUERY_DOC_TEMPLATE = (
    TEMPLATE_DIR / "datasource_query_doc.md.tmpl"
).read_text()

TYPE_MAP = {
    "string": "String",
    "integer": "Int64",
    "number": "Float64",
    "boolean": "Bool",
    "array": "List",
    "object": "String",  # object as JSON string
}


def find_latest_spec():
    specs = list(Path(".").glob("truenas-methods-*.json"))
    if not specs:
        print("ERROR: No spec file found. Run: make fetch-spec", file=sys.stderr)
        sys.exit(1)
    return sorted(specs)[-1]


def load_spec():
    spec_file = find_latest_spec()
    print(f"Using: {spec_file}", file=sys.stderr)
    with open(spec_file) as f:
        data = json.load(f)
    return data.get("methods", {}), data.get("_metadata", {})


def get_tf_type(prop_schema):
    """Convert JSON schema to Terraform type."""
    if isinstance(prop_schema, list):
        prop_schema = prop_schema[0] if prop_schema else {}
    if not isinstance(prop_schema, dict):
        return "String"

    # Handle anyOf/oneOf - check for actual type (nullable types)
    if "anyOf" in prop_schema:
        for variant in prop_schema["anyOf"]:
            if variant.get("type") == "integer":
                return "Int64"
            if variant.get("type") == "boolean":
                return "Bool"
            if variant.get("type") == "array":
                return "List"
        return "String"

    json_type = prop_schema.get("type")
    if "oneOf" in prop_schema or "discriminator" in prop_schema:
        return "String"  # Complex objects as JSON strings
    return TYPE_MAP.get(json_type, "String")


def generate_schema_attrs(
    properties, required, has_start=False, create_only_fields=None
):
    """Generate schema attributes for template."""
    if create_only_fields is None:
        create_only_fields = set()
    attrs = []

    # For datasources, id is always String (user input)
    # For resources, id is Computed and matches schema type
    if not has_start and not required:  # datasource mode
        attrs.append(
            '\t\t\t"id": schema.StringAttribute{Required: true, Description: "Resource ID"},'
        )
    elif "id" not in properties:
        attrs.append(
            '\t\t\t"id": schema.StringAttribute{Computed: true, Description: "Resource ID"},'
        )

    if has_start:
        attrs.append(
            '\t\t\t"start_on_create": schema.BoolAttribute{Optional: true, Description: "Start the resource immediately after creation (default: true)"},'
        )

    for name, prop in properties.items():
        # Skip id if already added, or if datasource mode (id handled separately)
        if name == "id":
            if (
                not has_start and not required
            ):  # datasource - skip, already added as String
                continue
            # For resources, add as Computed with actual type
            tf_type = get_tf_type(prop)
            attrs.append(
                f'\t\t\t"id": schema.{tf_type}Attribute{{Computed: true, Description: "Resource ID"}},'
            )
            continue
        # Skip reserved names
        if name in ["provider"]:
            continue
        if isinstance(prop, list):
            prop = prop[0] if prop else {}

        tf_type = get_tf_type(prop)
        is_req = name in required
        desc = (
            prop.get("description", "")[:100].replace('"', '\\"').replace("\n", " ")
            if isinstance(prop, dict)
            else ""
        )

        # Fix invalid attribute names
        attr_name = name.lower() if name != "CSR" else "csr"

        attrs.append(f'\t\t\t"{attr_name}": schema.{tf_type}Attribute{{')

        # For datasources (no required list), all attributes except id are Computed
        if not has_start and not required:  # datasource mode
            attrs.append(f"\t\t\t\tComputed: true,")
        else:  # resource mode
            # Check if field is auto-generated (optional + description mentions "generate")
            is_auto_generated = (
                not is_req
                and isinstance(prop, dict)
                and "generate" in prop.get("description", "").lower()
            )

            if is_auto_generated:
                # Optional + Computed for auto-generated fields
                attrs.append(f"\t\t\t\tOptional: true,")
                attrs.append(f"\t\t\t\tComputed: true,")
            else:
                attrs.append(f"\t\t\t\tRequired: {str(is_req).lower()},")
                attrs.append(f"\t\t\t\tOptional: {str(not is_req).lower()},")

        if tf_type == "List":
            attrs.append(f"\t\t\t\tElementType: types.StringType,")
        attrs.append(f'\t\t\t\tDescription: "{desc}",')

        # Add RequiresReplace for create-only fields (except 'name' which may support rename)
        if name in create_only_fields and name != "name":
            if tf_type == "String":
                attrs.append(
                    f"\t\t\t\tPlanModifiers: []planmodifier.String{{stringplanmodifier.RequiresReplace()}},"
                )
            elif tf_type == "Int64":
                attrs.append(
                    f"\t\t\t\tPlanModifiers: []planmodifier.Int64{{int64planmodifier.RequiresReplace()}},"
                )
            elif tf_type == "Bool":
                attrs.append(
                    f"\t\t\t\tPlanModifiers: []planmodifier.Bool{{boolplanmodifier.RequiresReplace()}},"
                )

        attrs.append("\t\t\t},")

    return "\n".join(attrs)


def generate_fields(properties, has_start=False):
    """Generate struct fields for template."""
    fields = []

    # For datasources, ID is always String (user input)
    # For resources, ID matches schema type or String if not in properties
    is_datasource = not has_start and "id" in properties
    if is_datasource:
        fields.append('\tID types.String `tfsdk:"id"`')
    elif "id" not in properties:
        fields.append('\tID types.String `tfsdk:"id"`')

    if has_start:
        fields.append('\tStartOnCreate types.Bool `tfsdk:"start_on_create"`')

    for name, prop in properties.items():
        # Skip reserved names and fix invalid names
        if name in ["provider"]:
            continue
        field_name = name.title().replace("_", "")
        if name == "CSR":
            field_name = "Csr"
        elif name == "id":
            if is_datasource:
                continue  # Already added as String
            field_name = "ID"
        tf_type = get_tf_type(prop)
        fields.append(f'\t{field_name} types.{tf_type} `tfsdk:"{name.lower()}"`')
    return "\n".join(fields)


def generate_create_params(properties):
    """Generate parameter building code for Create method."""
    lines = []
    for prop_name, prop_schema in properties.items():
        # Skip reserved names and id (id is not sent in create/update params)
        if prop_name in ["provider", "id"]:
            continue
        field_name = prop_name.title().replace("_", "")
        if prop_name == "CSR":
            field_name = "Csr"
        tf_type = get_tf_type(prop_schema)

        lines.append(f"\tif !data.{field_name}.IsNull() {{")

        if tf_type == "Bool":
            lines.append(f'\t\tparams["{prop_name}"] = data.{field_name}.ValueBool()')
        elif tf_type == "Int64":
            lines.append(f'\t\tparams["{prop_name}"] = data.{field_name}.ValueInt64()')
        elif tf_type == "Float64":
            lines.append(
                f'\t\tparams["{prop_name}"] = data.{field_name}.ValueFloat64()'
            )
        elif tf_type == "List":
            # Check if array contains complex objects
            array_has_objects = False
            if isinstance(prop_schema, dict):
                items = prop_schema.get("items")
                if items:
                    # items can be a list (tuple validation) or dict (single schema)
                    item_schema = items[0] if isinstance(items, list) else items
                    if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                        array_has_objects = True

            if array_has_objects:
                # Array of complex objects - expect JSON-encoded strings per element
                lines.append(f"\t\tvar {prop_name}List []string")
                lines.append(
                    f"\t\tdata.{field_name}.ElementsAs(ctx, &{prop_name}List, false)"
                )
                lines.append(f"\t\tvar {prop_name}Objs []map[string]interface{{}}")
                lines.append(f"\t\tfor _, jsonStr := range {prop_name}List {{")
                lines.append(f"\t\t\tvar obj map[string]interface{{}}")
                lines.append(f"\t\t\tif err := json.Unmarshal([]byte(jsonStr), &obj); err != nil {{")
                lines.append(
                    f'\t\t\t\tresp.Diagnostics.AddError("JSON Parse Error", fmt.Sprintf("Failed to parse {prop_name} item: %s", err))'
                )
                lines.append(f"\t\t\t\treturn")
                lines.append(f"\t\t\t}}")
                lines.append(f"\t\t\t{prop_name}Objs = append({prop_name}Objs, obj)")
                lines.append(f"\t\t}}")
                lines.append(f'\t\tparams["{prop_name}"] = {prop_name}Objs')
            else:
                # Array of primitives
                lines.append(f"\t\tvar {prop_name}List []string")
                lines.append(
                    f"\t\tdata.{field_name}.ElementsAs(ctx, &{prop_name}List, false)"
                )
                lines.append(f'\t\tparams["{prop_name}"] = {prop_name}List')
        else:
            # Check if this is a complex object that needs JSON parsing
            needs_json_parse = False
            if isinstance(prop_schema, dict):
                # Direct object type
                if prop_schema.get("type") == "object":
                    needs_json_parse = True
                # Check if anyOf/oneOf contains an object variant
                for key in ["anyOf", "oneOf"]:
                    if key in prop_schema:
                        for variant in prop_schema[key]:
                            if isinstance(variant, dict) and variant.get("type") == "object":
                                needs_json_parse = True
                                break
                # Discriminator indicates complex object
                if "discriminator" in prop_schema:
                    needs_json_parse = True

            if needs_json_parse:
                lines.append(f"\t\tvar {prop_name}Obj map[string]interface{{}}")
                lines.append(
                    f"\t\tif err := json.Unmarshal([]byte(data.{field_name}.ValueString()), &{prop_name}Obj); err != nil {{"
                )
                lines.append(
                    f'\t\t\tresp.Diagnostics.AddError("JSON Parse Error", fmt.Sprintf("Failed to parse {prop_name}: %s", err))'
                )
                lines.append(f"\t\t\treturn")
                lines.append(f"\t\t}}")
                lines.append(f'\t\tparams["{prop_name}"] = {prop_name}Obj')
            else:
                lines.append(
                    f'\t\tparams["{prop_name}"] = data.{field_name}.ValueString()'
                )

        lines.append("\t}")
    return "\n".join(lines)


def generate_read_mapping(
    properties,
    skip_id_for_datasource=False,
    create_only_fields=None,
    required_fields=None,
):
    """Generate code to map API response to Terraform state."""
    if create_only_fields is None:
        create_only_fields = set()
    if required_fields is None:
        required_fields = set()
    lines = []

    # Determine if we'll actually read any fields
    has_fields_to_read = False
    if not skip_id_for_datasource:
        has_fields_to_read = True
    else:
        for prop_name in properties.keys():
            if prop_name in ["provider", "id"]:
                continue
            if prop_name in create_only_fields and prop_name not in ["name", "type"]:
                continue
            if (
                required_fields is not None
                and prop_name not in required_fields
                and prop_name not in ["name", "type"]
            ):
                continue
            has_fields_to_read = True
            break

    # Only declare resultMap if we'll use it
    if has_fields_to_read:
        lines.append("\tresultMap, ok := result.(map[string]interface{})")
        lines.append("\tif !ok {")
        lines.append(
            '\t\tresp.Diagnostics.AddError("Parse Error", "Failed to parse API response")'
        )
        lines.append("\t\treturn")
        lines.append("\t}")
        lines.append("")
    else:
        # If we're not reading any fields, suppress unused variable warning
        lines.append("\t_ = result // No fields to read")
        lines.append("")

    # Always read back the ID field from API response (if present)
    if not skip_id_for_datasource:
        lines.append('\t\tif v, ok := resultMap["id"]; ok && v != nil {')
        lines.append('\t\t\tdata.ID = types.StringValue(fmt.Sprintf("%v", v))')
        lines.append("\t\t}")

    for prop_name, prop_schema in properties.items():
        # Skip reserved names
        if prop_name in ["provider"]:
            continue
        # Skip id for datasources (already set as String from input)
        if prop_name == "id" and skip_id_for_datasource:
            continue
        # Skip id in properties (handled above)
        if prop_name == "id":
            continue
        # Skip create-only fields - keep config/state value, don't overwrite from API
        # Exception: 'name' and 'type' should be read back as they're identifiers
        if prop_name in create_only_fields and prop_name not in ["name", "type"]:
            continue
        # For resources: only read back required fields and name/type
        # Optional fields should keep their config value (handled by Terraform)
        # For datasources (required_fields is None): read all fields
        if (
            required_fields is not None
            and prop_name not in required_fields
            and prop_name not in ["name", "type"]
        ):
            continue
        field_name = prop_name.title().replace("_", "")
        if prop_name == "CSR":
            field_name = "Csr"
        elif prop_name == "id":
            field_name = "ID"
        tf_type = get_tf_type(prop_schema)

        lines.append(f'\t\tif v, ok := resultMap["{prop_name}"]; ok && v != nil {{')

        if tf_type == "Bool":
            lines.append(
                f"\t\t\tif bv, ok := v.(bool); ok {{ data.{field_name} = types.BoolValue(bv) }}"
            )
        elif tf_type == "Int64":
            # Handle nested objects with 'parsed' field (e.g., quota, copies)
            lines.append(f"\t\t\tswitch val := v.(type) {{")
            lines.append(f"\t\t\tcase float64:")
            lines.append(f"\t\t\t\tdata.{field_name} = types.Int64Value(int64(val))")
            lines.append(f"\t\t\tcase map[string]interface{{}}:")
            lines.append(
                f'\t\t\t\tif parsed, ok := val["parsed"]; ok && parsed != nil {{'
            )
            lines.append(
                f"\t\t\t\t\tif fv, ok := parsed.(float64); ok {{ data.{field_name} = types.Int64Value(int64(fv)) }}"
            )
            lines.append(f"\t\t\t\t}}")
            lines.append(f"\t\t\t}}")
        elif tf_type == "Float64":
            lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ data.{field_name} = types.Float64Value(fv) }}"
            )
        elif tf_type == "List":
            lines.append(f"\t\t\tif arr, ok := v.([]interface{{}}); ok {{")
            lines.append(f"\t\t\t\tstrVals := make([]attr.Value, len(arr))")
            lines.append(
                f'\t\t\t\tfor i, item := range arr {{ strVals[i] = types.StringValue(fmt.Sprintf("%v", item)) }}'
            )
            lines.append(
                f"\t\t\t\tdata.{field_name}, _ = types.ListValue(types.StringType, strVals)"
            )
            lines.append(f"\t\t\t}}")
        else:
            # Handle nested objects with 'value' field (e.g., compression, atime)
            lines.append(f"\t\t\tswitch val := v.(type) {{")
            lines.append(f"\t\t\tcase string:")
            lines.append(f"\t\t\t\tdata.{field_name} = types.StringValue(val)")
            lines.append(f"\t\t\tcase map[string]interface{{}}:")
            lines.append(
                f'\t\t\t\tif strVal, ok := val["value"]; ok && strVal != nil {{'
            )
            lines.append(
                f'\t\t\t\t\tdata.{field_name} = types.StringValue(fmt.Sprintf("%v", strVal))'
            )
            lines.append(f"\t\t\t\t}}")
            lines.append(f"\t\t\tdefault:")
            lines.append(
                f'\t\t\t\tdata.{field_name} = types.StringValue(fmt.Sprintf("%v", v))'
            )
            lines.append(f"\t\t\t}}")

        lines.append("\t\t}")
    return "\n".join(lines)


def has_complex_objects(properties):
    """Check if any property needs JSON parsing."""
    for prop_name, prop_schema in properties.items():
        # Skip reserved names
        if prop_name in ["provider"]:
            continue
        if isinstance(prop_schema, dict):
            # Direct object type
            if prop_schema.get("type") == "object":
                return True
            # Check if anyOf/oneOf contains an object variant
            for key in ["anyOf", "oneOf"]:
                if key in prop_schema:
                    for variant in prop_schema[key]:
                        if isinstance(variant, dict) and variant.get("type") == "object":
                            return True
            # Discriminator indicates complex object
            if "discriminator" in prop_schema:
                return True
            # Check for arrays of complex objects
            if prop_schema.get("type") == "array":
                items = prop_schema.get("items")
                if items:
                    item_schema = items[0] if isinstance(items, list) else items
                    if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                        return True
    return False


def generate_resource(base_name, methods_dict, not_generated):
    """Generate resource file from method specs."""
    create_method = f"{base_name}.create"
    update_method = f"{base_name}.update"
    delete_method = f"{base_name}.delete"
    read_method = f"{base_name}.get_instance"

    if create_method in not_generated:
        del not_generated[create_method]
    if update_method in not_generated:
        del not_generated[update_method]
    if delete_method in not_generated:
        del not_generated[delete_method]

    # Check for lifecycle actions
    # Note: app.create already starts the app, so don't add start_on_create for apps
    has_start = f"{base_name}.start" in methods_dict and base_name != "app"
    has_stop = f"{base_name}.stop" in methods_dict

    # Check if methods are jobs
    create_spec = methods_dict.get(create_method, {})
    update_spec = methods_dict.get(update_method, {})
    delete_spec = methods_dict.get(delete_method, {})

    create_is_job = create_spec.get("job", False)
    update_is_job = update_spec.get("job", False)
    delete_is_job = delete_spec.get("job", False)

    # Detect ID type from update or delete method (first parameter)
    id_is_string = False
    for spec in [update_spec, delete_spec]:
        if spec and spec.get("accepts"):
            first_param = spec["accepts"][0]
            if first_param.get("type") == "string":
                id_is_string = True
                break

    # Get schema from create or update
    method_spec = create_spec or update_spec
    if not method_spec:
        return None

    accepts = method_spec.get("accepts", [])
    if not accepts:
        return None

    schema = accepts[0] if isinstance(accepts, list) else accepts

    # Handle anyOf schemas by merging all variants
    if "anyOf" in schema:
        merged_props = {}
        for variant in schema["anyOf"]:
            merged_props.update(variant.get("properties", {}))
        properties = merged_props
        # Only mark fields as required if they're required in ALL variants
        all_required = [set(variant.get("required", [])) for variant in schema["anyOf"]]
        required = list(set.intersection(*all_required)) if all_required else []
    else:
        properties = schema.get("properties", {})
        required = schema.get("required", [])

    if not properties:
        return None

    # Get update schema and merge with create (union approach - standard Terraform pattern)
    update_properties = {}
    create_only_fields = set()
    if update_spec and update_spec.get("accepts") and len(update_spec["accepts"]) >= 2:
        # Update has [id, data] format - get data schema (second parameter)
        update_schema = update_spec["accepts"][1]
        if "anyOf" in update_schema:
            for variant in update_schema["anyOf"]:
                update_properties.update(variant.get("properties", {}))
        elif update_schema.get("properties"):
            update_properties = update_schema["properties"]

        # Remove 'id' from update_properties - it's the resource identifier, not a field
        update_properties = {k: v for k, v in update_properties.items() if k != "id"}

        # Identify create-only fields (in create but not in update) - these need ForceNew
        create_only_fields = set(properties.keys()) - set(update_properties.keys())

        # Merge: union of create and update properties
        all_properties = {**properties, **update_properties}
        properties = all_properties
    else:
        # No update method or schema
        create_only_fields = set(properties.keys())
        update_properties = {}

    # Generate code
    resource_name = base_name.replace(".", "_").title().replace("_", "")
    tf_name = base_name.replace(".", "_")
    api_name = base_name

    # Choose Call or CallWithJob based on job flag
    create_call = "CallWithJob" if create_is_job else "Call"
    update_call = "CallWithJob" if update_is_job else "Call"
    delete_call = "CallWithJob" if delete_is_job else "Call"

    # Check if delete has optional parameters (needs [id, {}] format)
    delete_spec = methods_dict.get(f"{base_name}.delete", {})
    delete_accepts = delete_spec.get("accepts", [])
    delete_needs_options = len(delete_accepts) >= 2

    # Generate ID handling code based on type
    if id_is_string:
        id_read_code = "\tid = data.ID.ValueString()"
        id_update_code = "\tid = state.ID.ValueString()"
        if delete_needs_options:
            # Wrap in array with empty options object
            id_delete_code = (
                "\tid = []interface{}{data.ID.ValueString(), map[string]interface{}{}}"
            )
        else:
            id_delete_code = "\tid = data.ID.ValueString()"
    else:
        id_read_code = """	id, err = strconv.Atoi(data.ID.ValueString())
	if err != nil {{
		resp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))
		return
	}}"""
        id_update_code = """	id, err = strconv.Atoi(state.ID.ValueString())
	if err != nil {{
		resp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))
		return
	}}"""
        if delete_needs_options:
            # Wrap in array with empty options object
            id_delete_code = "\tid, err = strconv.Atoi(data.ID.ValueString())\n"
            id_delete_code += "\tif err != nil {\n"
            id_delete_code += '\t\tresp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))\n'
            id_delete_code += "\t\treturn\n"
            id_delete_code += "\t}\n"
            id_delete_code += "\tid = []interface{}{id, map[string]interface{}{}}"
        else:
            id_delete_code = """	id, err = strconv.Atoi(data.ID.ValueString())
	if err != nil {{
		resp.Diagnostics.AddError("Invalid ID", fmt.Sprintf("Cannot parse ID: %s", err))
		return
	}}"""

    # Generate lifecycle code if has start action
    lifecycle_code = ""
    if has_start:
        if id_is_string:
            lifecycle_code = f"""
\t// Handle lifecycle action - start on create if requested
\tstartOnCreate := true  // default when not specified
\tif !data.StartOnCreate.IsNull() {{
\t\tstartOnCreate = data.StartOnCreate.ValueBool()
\t}}
\tif startOnCreate {{
\t\t_, err = r.client.Call("{api_name}.start", data.ID.ValueString())
\t\tif err != nil {{
\t\t\tresp.Diagnostics.AddWarning("Start Failed", fmt.Sprintf("Resource created but failed to start: %s", err.Error()))
\t\t}}
\t}}"""
        else:
            lifecycle_code = f"""
\t// Handle lifecycle action - start on create if requested
\tstartOnCreate := true  // default when not specified
\tif !data.StartOnCreate.IsNull() {{
\t\tstartOnCreate = data.StartOnCreate.ValueBool()
\t}}
\tif startOnCreate {{
\t\tvmID, err := strconv.Atoi(data.ID.ValueString())
\t\tif err != nil {{
\t\t\tresp.Diagnostics.AddError("ID Conversion Error", fmt.Sprintf("Failed to convert ID to integer: %s", err.Error()))
\t\t\treturn
\t\t}}
\t\t_, err = r.client.Call("{api_name}.start", vmID)
\t\tif err != nil {{
\t\t\tresp.Diagnostics.AddWarning("Start Failed", fmt.Sprintf("Resource created but failed to start: %s", err.Error()))
\t\t}}
\t}}"""

    # Determine if strconv import is needed (for int IDs or lifecycle/predelete code with int IDs)
    needs_strconv = (not id_is_string) or (has_start and not id_is_string) or (has_stop and not id_is_string)
    extra_imports = '\t"strconv"' if needs_strconv else ""

    # Check if any List fields exist that will be used in read mapping
    # For resources: only required List fields
    # For datasources: all List fields
    has_list = any(
        get_tf_type(p) == "List"
        and (name not in create_only_fields or name in ["name", "type"])
        and (name in required or name in ["name", "type"])
        for name, p in properties.items()
    )
    # Check if any complex objects need JSON parsing
    has_json = has_complex_objects(properties)

    # Check which plan modifiers are needed for create-only fields
    needs_string_planmod = False
    needs_int64_planmod = False
    needs_bool_planmod = False
    for field in create_only_fields:
        if field != "name" and field in properties:
            tf_type = get_tf_type(properties[field])
            if tf_type == "String":
                needs_string_planmod = True
            elif tf_type == "Int64":
                needs_int64_planmod = True
            elif tf_type == "Bool":
                needs_bool_planmod = True

    # Only add attr import if we actually have required List fields
    if has_list and required:
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/attr"'
    if has_json:
        extra_imports += '\n\t"encoding/json"'
    if has_stop:
        extra_imports += '\n\t"time"'
    if needs_string_planmod or needs_int64_planmod or needs_bool_planmod:
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"'
    if needs_string_planmod:
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"'
    if needs_int64_planmod:
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/resource/schema/int64planmodifier"'
    if needs_bool_planmod:
        extra_imports += '\n\t"github.com/hashicorp/terraform-plugin-framework/resource/schema/boolplanmodifier"'

    # Get description from method spec
    description = method_spec.get("description", f"TrueNAS {tf_name} resource")
    if description:
        description = description.split("\n")[0][:200].replace('"', '\\"')

    # Generate pre-delete code if has stop action
    predelete_code = ""
    if has_stop:
        if id_is_string:
            predelete_code = f"""
\t// Stop app before deletion if running
\t_, _ = r.client.Call("{api_name}.stop", data.ID.ValueString())  // Ignore errors - app might already be stopped
\ttime.Sleep(2 * time.Second)  // Wait for app to stop
"""
        else:
            predelete_code = f"""
\t// Stop VM before deletion if running
\tvmID, err := strconv.Atoi(data.ID.ValueString())
\tif err != nil {{
\t\tresp.Diagnostics.AddError("ID Conversion Error", fmt.Sprintf("Failed to convert ID to integer: %s", err.Error()))
\t\treturn
\t}}
\t_, _ = r.client.Call("{api_name}.stop", vmID)  // Ignore errors - VM might already be stopped
\ttime.Sleep(2 * time.Second)  // Wait for VM to stop
"""

    # Use special template for vm.device
    if api_name == "vm.device":
        code = RESOURCE_VM_DEVICE_TEMPLATE.format(
            resource_name=resource_name,
            name=tf_name,
            api_name=api_name,
            fields=generate_fields(properties, has_start),
            schema_attrs=generate_schema_attrs(
                properties, required, has_start, create_only_fields
            ),
            create_params=generate_create_params(properties),
            read_mapping=generate_read_mapping(
                properties,
                create_only_fields=create_only_fields,
                required_fields=set(required),
            ),
            lifecycle_code=lifecycle_code,
        )
    else:
        code = RESOURCE_TEMPLATE.format(
            resource_name=resource_name,
            name=tf_name,
            api_name=api_name,
            description=description,
            fields=generate_fields(properties, has_start),
            schema_attrs=generate_schema_attrs(
                properties, required, has_start, create_only_fields
            ),
            create_params=generate_create_params(properties),
            update_params=generate_create_params(
                update_properties if update_properties else properties
            ),
            read_mapping=generate_read_mapping(
                properties,
                create_only_fields=create_only_fields,
                required_fields=set(required),
            ),
            lifecycle_code=lifecycle_code,
            predelete_code=predelete_code,
            id_read_code=id_read_code,
            id_update_code=id_update_code,
            id_delete_code=id_delete_code,
            extra_imports=extra_imports,
            create_call=create_call,
            update_call=update_call,
            delete_call=delete_call,
        )

    return code


def generate_action_resource(method_name, method_spec, not_generated):
    """Generate action resource from method spec."""
    # Parse method name (e.g., "pool.scrub" -> "pool", "scrub")
    parts = method_name.split(".")
    if len(parts) < 2:
        return None

    base_name = ".".join(parts[:-1])
    action_name = parts[-1]

    # Build resource name (e.g., "ActionPoolScrub")
    resource_name = "Action" + "".join(p.title() for p in parts)
    resource_type_name = f"action_{method_name.replace('.', '_')}"

    if method_name in not_generated:
        del not_generated[method_name]

    # Get parameters
    accepts = method_spec.get("accepts", [])
    if not accepts:
        return None

    # Build schema from parameters
    properties = {}
    for param in accepts:
        param_name = param.get("_name_", "")
        if not param_name:
            continue
        properties[param_name] = param

    if not properties:
        return None

    # Generate input fields (without computed outputs)
    input_fields = []
    for prop_name, prop_schema in properties.items():
        field_name = "".join(p.title() for p in prop_name.split("_"))
        tf_type = get_tf_type(prop_schema)
        # For List/Object types, use String (JSON) to avoid complexity
        if tf_type in ["List", "Object"]:
            tf_type = "String"
        input_fields.append(f'\t{field_name} types.{tf_type} `tfsdk:"{prop_name}"`')

    fields = "\n".join(input_fields)

    # Generate schema attributes for inputs (Required or Optional)
    schema_lines = []
    for prop_name, prop_schema in properties.items():
        field_name = "".join(p.title() for p in prop_name.split("_"))
        tf_type = get_tf_type(prop_schema)
        required = prop_schema.get("_required_", False)
        description = (
            prop_schema.get("description", "")
            .replace('"', '\\"')
            .replace("\n", " ")[:200]
        )

        # For List/Object types, use String (JSON) to avoid ElementType complexity
        if tf_type in ["List", "Object"]:
            tf_type = "String"

        if required:
            schema_lines.append(f'\t\t\t"{prop_name}": schema.{tf_type}Attribute{{')
            schema_lines.append(f"\t\t\t\tRequired: true,")
            schema_lines.append(f'\t\t\t\tMarkdownDescription: "{description}",')
            schema_lines.append("\t\t\t},")
        else:
            schema_lines.append(f'\t\t\t"{prop_name}": schema.{tf_type}Attribute{{')
            schema_lines.append(f"\t\t\t\tOptional: true,")
            schema_lines.append(f'\t\t\t\tMarkdownDescription: "{description}",')
            schema_lines.append("\t\t\t},")

    schema_attrs = "\n".join(schema_lines)

    # Generate parameter building code
    param_lines = []
    param_lines.append("\t// Build parameters as array (positional)")
    param_lines.append("\tparams := []interface{}{}")
    needs_json = False

    for prop_name, prop_schema in properties.items():
        field_name = "".join(p.title() for p in prop_name.split("_"))
        tf_type = get_tf_type(prop_schema)
        required = prop_schema.get("_required_", False)

        # For List/Object, we store as String (JSON) and need to parse
        if tf_type in ["List", "Object"]:
            needs_json = True
            if required:
                param_lines.append(f"\tvar {prop_name}Val interface{{}}")
                param_lines.append(
                    f"\tif err := json.Unmarshal([]byte(data.{field_name}.ValueString()), &{prop_name}Val); err == nil {{"
                )
                param_lines.append(f"\t\tparams = append(params, {prop_name}Val)")
                param_lines.append("\t}")
            else:
                param_lines.append(f"\tif !data.{field_name}.IsNull() {{")
                param_lines.append(f"\t\tvar {prop_name}Val interface{{}}")
                param_lines.append(
                    f"\t\tif err := json.Unmarshal([]byte(data.{field_name}.ValueString()), &{prop_name}Val); err == nil {{"
                )
                param_lines.append(f"\t\t\tparams = append(params, {prop_name}Val)")
                param_lines.append("\t\t}")
                param_lines.append("\t}")
        else:
            if required:
                if tf_type == "String":
                    param_lines.append(
                        f"\tparams = append(params, data.{field_name}.ValueString())"
                    )
                elif tf_type == "Int64":
                    param_lines.append(
                        f"\tparams = append(params, data.{field_name}.ValueInt64())"
                    )
                elif tf_type == "Bool":
                    param_lines.append(
                        f"\tparams = append(params, data.{field_name}.ValueBool())"
                    )
                elif tf_type == "Float64":
                    param_lines.append(
                        f"\tparams = append(params, data.{field_name}.ValueFloat64())"
                    )
            else:
                param_lines.append(f"\tif !data.{field_name}.IsNull() {{")
                if tf_type == "String":
                    param_lines.append(
                        f"\t\tparams = append(params, data.{field_name}.ValueString())"
                    )
                elif tf_type == "Int64":
                    param_lines.append(
                        f"\t\tparams = append(params, data.{field_name}.ValueInt64())"
                    )
                elif tf_type == "Bool":
                    param_lines.append(
                        f"\t\tparams = append(params, data.{field_name}.ValueBool())"
                    )
                elif tf_type == "Float64":
                    param_lines.append(
                        f"\t\tparams = append(params, data.{field_name}.ValueFloat64())"
                    )
                param_lines.append("\t}")

    param_building = "\n".join(param_lines)

    # Check if this is a job
    is_job = method_spec.get("job", False)

    # Get description
    description = method_spec.get("description") or f"Execute {method_name} action"
    description = description.replace('"', '\\"').replace("\n", " ").split(".")[0][:200]

    # Build extra imports
    extra_imports = ""
    if needs_json:
        extra_imports = '\n\t"encoding/json"'

    # Generate code from template
    code = ACTION_RESOURCE_TEMPLATE
    code = code.replace("{resource_name}", resource_name)
    code = code.replace("{resource_type_name}", resource_type_name)
    code = code.replace("{fields}", fields)
    code = code.replace("{schema_attrs}", schema_attrs)
    code = code.replace("{param_building}", param_building)
    code = code.replace("{method_name}", method_name)
    code = code.replace("{description}", description)
    code = code.replace("{is_job}", "true" if is_job else "false")
    code = code.replace("{extra_imports}", extra_imports)

    return code


def generate_attr_types(properties):
    """Generate AttrTypes map for ListValueFrom"""
    lines = []
    for name, prop in sorted(properties.items()):
        if name in ["provider"]:
            continue
        tf_type = get_tf_type(prop)
        # Skip List types - too complex for query datasources
        if tf_type == "List":
            continue
        # ID is always String in datasources
        if name == "id":
            tf_type = "String"
        attr_name = name.lower() if name != "CSR" else "csr"

        if tf_type == "String":
            lines.append(f'\t\t\t"{attr_name}": types.StringType,')
        elif tf_type == "Int64":
            lines.append(f'\t\t\t"{attr_name}": types.Int64Type,')
        elif tf_type == "Bool":
            lines.append(f'\t\t\t"{attr_name}": types.BoolType,')
        elif tf_type == "Float64":
            lines.append(f'\t\t\t"{attr_name}": types.Float64Type,')
    return "\n".join(lines)


def generate_query_datasource(base_name, methods_dict, not_generated):
    """Generate query data source for listing multiple resources."""
    query_method = f"{base_name}.query"

    if query_method in not_generated:
        del not_generated[query_method]

    query_spec = methods_dict.get(query_method, {})
    if not query_spec:
        return None

    # Get return schema
    returns = query_spec.get("returns", [])
    if not returns:
        return None

    # Query returns array of items - handle anyOf wrapper
    schema = returns[0] if isinstance(returns, list) else returns

    # Handle anyOf - look for array type
    if "anyOf" in schema:
        for variant in schema["anyOf"]:
            if isinstance(variant, dict) and variant.get("type") == "array":
                schema = variant
                break

    if schema.get("type") != "array":
        return None

    items_schema = schema.get("items", {})
    if isinstance(items_schema, list):
        items_schema = items_schema[0] if items_schema else {}

    properties = items_schema.get("properties", {})
    if not properties:
        return None

    # Filter out List types - too complex for query datasources
    filtered_properties = {
        k: v for k, v in properties.items() if get_tf_type(v) != "List"
    }
    if not filtered_properties:
        return None

    # Generate code
    resource_name = base_name.replace(".", "_").title().replace("_", "") + "s"  # Plural
    tf_name = base_name.replace(".", "_") + "s"  # Plural
    api_name = base_name
    description = query_spec.get("description") or f"Query {tf_name} resources"
    description = description.split("\n")[0][:200].replace('"', '\\"')

    # Generate read mapping for items
    read_mapping_lines = []
    for prop_name, prop_schema in filtered_properties.items():
        if prop_name in ["provider"]:
            continue
        field_name = prop_name.title().replace("_", "")
        if prop_name == "CSR":
            field_name = "Csr"
        elif prop_name == "id":
            field_name = "ID"
        tf_type = get_tf_type(prop_schema)

        read_mapping_lines.append(
            f'\t\tif v, ok := resultMap["{prop_name}"]; ok && v != nil {{'
        )
        if tf_type == "Bool":
            read_mapping_lines.append(
                f"\t\t\tif bv, ok := v.(bool); ok {{ itemModel.{field_name} = types.BoolValue(bv) }}"
            )
        elif (
            tf_type == "Int64" and prop_name != "id"
        ):  # ID is always String in datasources
            read_mapping_lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ itemModel.{field_name} = types.Int64Value(int64(fv)) }}"
            )
        elif tf_type == "Float64":
            read_mapping_lines.append(
                f"\t\t\tif fv, ok := v.(float64); ok {{ itemModel.{field_name} = types.Float64Value(fv) }}"
            )
        elif tf_type == "List":
            read_mapping_lines.append(f"\t\t\t// Skip complex list types for now")
        else:
            read_mapping_lines.append(
                f'\t\t\titemModel.{field_name} = types.StringValue(fmt.Sprintf("%v", v))'
            )
        read_mapping_lines.append("\t\t}")

    code = DATASOURCE_QUERY_TEMPLATE.format(
        resource_name=resource_name,
        name=tf_name,
        api_name=api_name,
        description=description,
        fields=generate_fields(filtered_properties, False),
        schema_attrs=generate_schema_attrs(filtered_properties, [], False),
        read_mapping="\n".join(read_mapping_lines),
        attr_types=generate_attr_types(filtered_properties),
    )

    return code


def generate_datasource(base_name, methods_dict, not_generated: dict):
    """Generate data source file from method specs."""
    get_method = f"{base_name}.get_instance"

    if get_method in not_generated:
        del not_generated[get_method]

    get_spec = methods_dict.get(get_method, {})
    if not get_spec:
        return None

    # Get return schema
    returns = get_spec.get("returns", [])
    if not returns:
        return None

    schema = returns[0] if isinstance(returns, list) else returns
    properties = schema.get("properties", {})

    if not properties:
        return None

    # Datasources read all fields, so no attr import needed (List fields are skipped in read mapping)
    extra_imports = ""

    # Determine ID type and parameter format from schema
    id_type = get_tf_type(properties.get("id", {"type": "string"}))
    if id_type == "Int64":
        # ID in schema is Int64, but datasource input is String - convert
        id_param = (
            "func() int { id, _ := strconv.Atoi(data.ID.ValueString()); return id }()"
        )
        extra_imports += '\n\t"strconv"'
    else:
        id_param = "data.ID.ValueString()"

    # Generate code
    resource_name = base_name.replace(".", "_").title().replace("_", "")
    tf_name = base_name.replace(".", "_")
    api_name = base_name
    description = get_spec.get("description") or f"Retrieves TrueNAS {tf_name} data"
    description = description.split("\n")[0][:200].replace('"', '\\"')

    code = DATASOURCE_TEMPLATE.format(
        resource_name=resource_name,
        name=tf_name,
        api_name=api_name,
        description=description,
        fields=generate_fields(properties, False),
        schema_attrs=generate_schema_attrs(properties, [], False),
        read_mapping=generate_read_mapping(properties, skip_id_for_datasource=True),
        extra_imports=extra_imports,
        id_param=id_param,
    )

    return code


def generate_datasource_docs(base_name, properties, description):
    """Generate data source documentation"""
    tf_name = base_name.replace(".", "_")

    # Build attributes list
    attrs = []
    for name, prop in sorted(properties.items()):
        if name in ["id"]:
            continue
        tf_type = get_tf_type(prop)
        desc = prop.get("description", "") if isinstance(prop, dict) else ""
        desc = desc.replace("\n", " ").strip()[:200]
        attrs.append(f"- `{name}` ({tf_type}) - {desc}")

    doc = DATASOURCE_DOC_TEMPLATE.format(
        resource_type=tf_name,
        description=description,
        name=tf_name,
        attrs=chr(10).join(attrs) if attrs else "- None",
    )

    docs_dir = Path("docs/data-sources")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / f"{tf_name}.md").write_text(doc)


def generate_query_datasource_docs(base_name, properties, description):
    """Generate query data source documentation"""
    tf_name = base_name.replace(".", "_") + "s"  # Plural

    # Build attributes list
    attrs = []
    for name, prop in sorted(properties.items()):
        if name in ["id"]:
            continue
        tf_type = get_tf_type(prop)
        desc = prop.get("description", "") if isinstance(prop, dict) else ""
        desc = desc.replace("\n", " ").strip()[:200]
        attrs.append(f"- `{name}` ({tf_type}) - {desc}")

    doc = DATASOURCE_QUERY_DOC_TEMPLATE.format(
        resource_type=tf_name,
        description=description,
        name=base_name.replace(".", "_"),
        attrs=chr(10).join(attrs) if attrs else "- None",
    )

    docs_dir = Path("docs/data-sources")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / f"{tf_name}.md").write_text(doc)


def generate_resource_docs(
    base_name, properties, required, description, methods_dict, anyof_variants=None
):
    """Generate Terraform documentation markdown"""
    tf_name = base_name.replace(".", "_")
    has_start = f"{base_name}.start" in methods_dict

    # Detect discriminator field for anyOf schemas
    discriminator_field = None
    variant_info = {}
    discriminator_all_values = []

    if anyof_variants:
        # Find discriminator field (usually 'type')
        for field_name in ["type", "kind", "variant"]:
            if field_name in properties:
                prop = properties[field_name]
                if isinstance(prop, dict) and "enum" in prop:
                    discriminator_field = field_name
                    break

        # Build variant information and collect all discriminator values
        for variant in anyof_variants:
            variant_props = variant.get("properties", {})
            variant_required = set(variant.get("required", []))

            # Identify variant by discriminator value
            variant_name = None
            if discriminator_field and discriminator_field in variant_props:
                disc_prop = variant_props[discriminator_field]
                if isinstance(disc_prop, dict):
                    if "enum" in disc_prop and disc_prop["enum"]:
                        variant_name = disc_prop["enum"][0]
                        discriminator_all_values.extend(disc_prop["enum"])
                    elif "default" in disc_prop:
                        variant_name = disc_prop["default"]
                        discriminator_all_values.append(disc_prop["default"])

            if variant_name:
                variant_info[variant_name] = {
                    "properties": set(variant_props.keys()),
                    "required": variant_required,
                }

    # Build example with required fields
    example_lines = []
    for name in sorted(required):
        if name in properties and name not in ["uuid", "id"]:
            prop = properties[name]
            tf_type = get_tf_type(prop)
            if tf_type == "String":
                example_lines.append(f'  {name} = "example-value"')
            elif tf_type == "Int64":
                example_lines.append(f"  {name} = 1")
            elif tf_type == "Bool":
                example_lines.append(f"  {name} = true")
            elif tf_type == "Float64":
                example_lines.append(f"  {name} = 1.0")
            elif tf_type == "List":
                # Check if array contains complex objects
                if isinstance(prop, dict):
                    items = prop.get("items")
                    if items:
                        item_schema = items[0] if isinstance(items, list) else items
                        if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                            # Array of complex objects - show jsonencode example
                            example_lines.append(f"  {name} = [")
                            example_lines.append(f"    jsonencode({{")
                            example_lines.append(f"      # Configure object fields")
                            example_lines.append(f"    }})")
                            example_lines.append(f"  ]")
                            continue
                # Simple array
                example_lines.append(f'  {name} = ["item1"]')

    if has_start and len(example_lines) < 8:
        example_lines.append("  start_on_create = true")

    # Build schema documentation
    required_args = []
    optional_args = []

    if has_start:
        optional_args.append(
            "- `start_on_create` (Bool) - Start the resource immediately after creation. Default: `true`"
        )

    for name, prop in sorted(properties.items()):
        if name in ["provider", "uuid", "id"]:
            continue
        tf_type = get_tf_type(prop)
        desc = prop.get("description", "") if isinstance(prop, dict) else ""
        desc = desc.replace("\n", " ").strip()[:200]

        # Check if this is a JSON object type (only for String types that represent objects)
        is_json_object = False
        if tf_type == "String" and isinstance(prop, dict):
            # Direct object type
            if prop.get("type") == "object" and "properties" in prop:
                is_json_object = True
            # Check if anyOf/oneOf contains an object variant
            for key in ["anyOf", "oneOf"]:
                if key in prop:
                    for variant in prop[key]:
                        if isinstance(variant, dict) and variant.get("type") == "object":
                            is_json_object = True
                            break

            if is_json_object:
                desc += " **Note:** This is a JSON object. Use `jsonencode()` to pass structured data."

                # Try to show object structure from anyOf/oneOf
                obj_schema = None
                if "anyOf" in prop:
                    # Find the object variant (skip null)
                    for variant in prop["anyOf"]:
                        if variant.get("type") == "object" and "properties" in variant:
                            obj_schema = variant
                            break
                elif "oneOf" in prop:
                    for variant in prop["oneOf"]:
                        if variant.get("type") == "object" and "properties" in variant:
                            obj_schema = variant
                            break
                elif prop.get("type") == "object" and "properties" in prop:
                    obj_schema = prop

                # Add example structure
                if obj_schema and "properties" in obj_schema:
                    obj_props = obj_schema["properties"]
                    if obj_props:
                        desc += " Example: `jsonencode({"
                        prop_examples = []
                        for obj_prop_name, obj_prop in list(obj_props.items())[:3]:
                            obj_prop_type = obj_prop.get("type", "string")
                            if obj_prop_type == "string":
                                prop_examples.append(f'{obj_prop_name} = "value"')
                            elif obj_prop_type == "integer":
                                prop_examples.append(f"{obj_prop_name} = 0")
                            elif obj_prop_type == "boolean":
                                prop_examples.append(f"{obj_prop_name} = true")
                        desc += ", ".join(prop_examples)
                        if len(obj_props) > 3:
                            desc += ", ..."
                        desc += "})`"

        # Add default value if present
        if isinstance(prop, dict) and "default" in prop:
            desc += f" Default: `{prop['default']}`"

        # Add note for arrays of complex objects
        if tf_type == "List" and isinstance(prop, dict):
            items = prop.get("items")
            if items:
                item_schema = items[0] if isinstance(items, list) else items
                if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                    desc += " **Note:** Each element must be a JSON-encoded object."

                    # Show object structure from item schema
                    if "properties" in item_schema:
                        obj_props = item_schema["properties"]
                        obj_required = set(item_schema.get("required", []))
                        if obj_props:
                            desc += " Example: `[jsonencode({"
                            prop_examples = []
                            for obj_prop_name, obj_prop in list(obj_props.items())[:4]:
                                is_req = obj_prop_name in obj_required
                                req_marker = "" if is_req else " (optional)"
                                obj_prop_type = obj_prop.get("type", "string")
                                if obj_prop_type == "string":
                                    prop_examples.append(f'{obj_prop_name} = "..."{req_marker}')
                                elif obj_prop_type == "integer":
                                    prop_examples.append(f'{obj_prop_name} = 0{req_marker}')
                                elif obj_prop_type == "boolean":
                                    prop_examples.append(f'{obj_prop_name} = true{req_marker}')
                            desc += ", ".join(prop_examples)
                            if len(obj_props) > 4:
                                desc += ", ..."
                            desc += "})]`"

        # Add enum values if present
        if isinstance(prop, dict) and "enum" in prop:
            # For discriminator field in anyOf schemas, show all variant values
            if name == discriminator_field and discriminator_all_values:
                enum_vals = ", ".join(
                    f"`{v}`" for v in sorted(set(discriminator_all_values))[:10]
                )
            else:
                enum_vals = ", ".join(f"`{v}`" for v in prop["enum"][:10])
            desc += f" Valid values: {enum_vals}"

        # Add variant applicability if this is an anyOf schema
        if variant_info and name != discriminator_field:
            applicable_variants = [
                v for v, info in variant_info.items() if name in info["properties"]
            ]
            if applicable_variants and len(applicable_variants) < len(variant_info):
                variant_list = ", ".join(f"`{v}`" for v in applicable_variants)
                desc += f" **Applies to:** {variant_list}"

        arg_line = f"- `{name}` ({tf_type}) - {desc}"

        if name in required:
            required_args.append(arg_line)
        else:
            optional_args.append(arg_line)

    # Build variant examples if anyOf present
    variant_examples = ""
    if variant_info and discriminator_field:
        variant_examples = "\n\n## Variants\n\n"
        variant_examples += f"This resource has **{len(variant_info)} variants** controlled by the `{discriminator_field}` field. "
        variant_examples += "Choose the appropriate variant for your use case:\n\n"

        for variant_name, info in sorted(variant_info.items()):
            variant_examples += f"### {variant_name}\n\n"

            # Build example for this variant
            variant_example_lines = []
            variant_required = sorted(info["required"] - {"provider", "uuid", "id"})

            # Add discriminator field first
            variant_example_lines.append(f'  {discriminator_field} = "{variant_name}"')

            # Add other required fields
            for req_field in variant_required:
                if req_field == discriminator_field:
                    continue
                if req_field in properties:
                    prop = properties[req_field]
                    tf_type = get_tf_type(prop)
                    if tf_type == "String":
                        variant_example_lines.append(f'  {req_field} = "value"')
                    elif tf_type == "Int64":
                        variant_example_lines.append(f"  {req_field} = 1024")
                    elif tf_type == "Bool":
                        variant_example_lines.append(f"  {req_field} = true")

            # Show example
            variant_examples += "```terraform\n"
            variant_examples += f'resource "truenas_{tf_name}" "example" {{\n'
            variant_examples += "\n".join(variant_example_lines)
            variant_examples += "\n}\n```\n\n"

            # Show required fields
            if variant_required:
                variant_examples += (
                    "**Required fields:** "
                    + ", ".join(f"`{r}`" for r in variant_required)
                    + "\n\n"
                )

            # Show variant-specific optional fields (not in all variants)
            variant_props = info["properties"] - {"provider", "uuid", "id"}
            all_props = set()
            for v_info in variant_info.values():
                all_props.update(v_info["properties"])
            variant_specific = sorted(
                (
                    variant_props
                    - all_props.intersection(
                        *[v["properties"] for v in variant_info.values()]
                    )
                )
                - info["required"]
            )

            if variant_specific:
                variant_examples += "**Key optional fields:** " + ", ".join(
                    f"`{p}`" for p in variant_specific[:8]
                )
                if len(variant_specific) > 8:
                    variant_examples += f" (and {len(variant_specific) - 8} more)"
                variant_examples += "\n\n"

    # Build generic example section (skip for anyOf resources)
    generic_example = ""
    if not variant_info:
        generic_example = "\n## Example Usage\n\n```terraform\n"
        generic_example += f'resource "truenas_{tf_name}" "example" {{\n'
        generic_example += (
            chr(10).join(example_lines)
            if example_lines
            else "  # Configure required attributes"
        )
        generic_example += "\n}\n```\n"

    doc = RESOURCE_DOC_TEMPLATE.format(
        resource_type=tf_name,
        description=description,
        required_args=chr(10).join(required_args) if required_args else "- None",
        optional_args=chr(10).join(optional_args) if optional_args else "- None",
        variant_examples=variant_examples,
        generic_example=generic_example,
    )

    docs_dir = Path("docs/resources")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / f"{tf_name}.md").write_text(doc)


def generate_provider(resources, datasources, actions):
    """Generate provider.go from template"""


def generate_action_docs(method_name, properties, description):
    """Generate documentation for action resources"""
    resource_name = f"action_{method_name.replace('.', '_')}"

    # Build example
    example_lines = [f'resource "truenas_{resource_name}" "example" {{']
    for prop_name, prop_schema in properties.items():
        tf_type = get_tf_type(prop_schema)
        required = prop_schema.get("_required_", False)

        if required:
            if tf_type == "String":
                example_lines.append(f'  {prop_name} = "value"')
            elif tf_type == "Int64":
                example_lines.append(f"  {prop_name} = 1")
            elif tf_type == "Bool":
                example_lines.append(f"  {prop_name} = true")
    example_lines.append("}")
    example = "\n".join(example_lines)

    # Build schema
    schema_lines = []
    for prop_name, prop_schema in properties.items():
        tf_type = get_tf_type(prop_schema)
        required = prop_schema.get("_required_", False)
        prop_desc = prop_schema.get("description", "").replace("\n", " ")[:200]

        req_opt = "Required" if required else "Optional"
        schema_lines.append(f"- `{prop_name}` ({tf_type}, {req_opt}) {prop_desc}")

    # Add computed outputs
    schema_lines.append("")
    schema_lines.append("### Computed Outputs")
    schema_lines.append("")
    schema_lines.append(
        "- `action_id` (String) Unique identifier for this action execution"
    )
    schema_lines.append("- `job_id` (Int64) Background job ID (if applicable)")
    schema_lines.append("- `state` (String) Job state: SUCCESS, FAILED, or RUNNING")
    schema_lines.append("- `progress` (Float64) Job progress percentage (0-100)")
    schema_lines.append("- `result` (String) Action result data")
    schema_lines.append("- `error` (String) Error message if action failed")

    schema = "\n".join(schema_lines)

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

{schema}

## Notes

- Actions execute immediately when the resource is created
- Background jobs are monitored until completion
- Progress updates are logged during execution
- The resource cannot be updated - changes force recreation
- Destroying the resource does not undo the action
"""

    docs_dir = Path("docs/resources")
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / f"{resource_name}.md").write_text(doc)


def generate_provider(resources, datasources, actions):
    """Generate provider.go from template"""
    with open("templates/provider.go.tmpl", "r") as f:
        template = f.read()

    # Build resource list (CRUD resources)
    resource_funcs = [
        f"New{r.replace('.', '_').title().replace('_', '')}Resource" for r in resources
    ]

    # Add manual resources (special cases)
    manual_resources = [
        "NewFilesystemPutResource",  # HTTP multipart upload
    ]

    # Build action resource list (with Action prefix)
    action_funcs = [
        f"NewAction{''.join(p.title() for p in a.split('.'))}Resource" for a in actions
    ]

    # Combine all resources
    all_resource_funcs = resource_funcs + manual_resources + action_funcs
    resource_list = ",\n\t\t".join(all_resource_funcs)

    # Build datasource list
    datasource_funcs = [
        f"New{d.replace('.', '_').title().replace('_', '')}DataSource"
        for d in datasources
    ]
    datasource_list = ",\n\t\t".join(datasource_funcs)
    if datasource_list:
        datasource_list += ","  # Add trailing comma

    # Replace template variables
    code = template.replace("{{resource_list}}", resource_list)
    code = code.replace("{{datasource_list}}", datasource_list)

    with open("internal/provider/provider.go", "w") as f:
        f.write(code)

    print("✅ Generated provider.go", file=sys.stderr)


def main():
    print("=" * 60, file=sys.stderr)
    print("TrueNAS Provider Generator (Native Spec)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    methods, metadata = load_spec()
    print(f"Version: {metadata.get('truenas_version')}", file=sys.stderr)
    print(f"Methods: {len(methods)}", file=sys.stderr)

    not_generated = copy.deepcopy(methods)
    # Find resources
    resources = {}
    for method_name in methods.keys():
        if method_name.endswith(".create"):
            base = method_name[:-7]
            resources[base] = methods

    print(f"Resources: {len(resources)}", file=sys.stderr)

    # Generate
    output_dir = Path("internal/provider")
    count = 0
    generated_resources = []

    # Skip resources with complex array handling for now
    skip_resources = {
        "nvmet.port",  # No properties in create schema
    }

    for base_name in resources.keys():
        if base_name in skip_resources:
            continue
        code = generate_resource(base_name, methods, not_generated)
        if code:
            filename = f"resource_{base_name.replace('.', '_')}_generated.go"
            (output_dir / filename).write_text(code)
            generated_resources.append(base_name)
            count += 1

            # Generate documentation
            create_spec = methods.get(f"{base_name}.create", {})
            accepts = create_spec.get("accepts", [])
            if accepts:
                schema = accepts[0] if isinstance(accepts, list) else accepts

                # Handle anyOf schemas by merging all variants (same as resource generation)
                anyof_variants = None
                if "anyOf" in schema:
                    anyof_variants = schema["anyOf"]
                    merged_props = {}
                    for variant in schema["anyOf"]:
                        merged_props.update(variant.get("properties", {}))
                    properties = merged_props
                    # Only mark fields as required if they're required in ALL variants
                    all_required = [
                        set(variant.get("required", [])) for variant in schema["anyOf"]
                    ]
                    required = (
                        list(set.intersection(*all_required)) if all_required else []
                    )
                else:
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])

                description = (
                    create_spec.get("description")
                    or f"Manages TrueNAS {base_name} resources"
                )
                description = description.split("\n")[0][:200]
                generate_resource_docs(
                    base_name,
                    properties,
                    required,
                    description,
                    methods,
                    anyof_variants,
                )

    print(f"\n✅ Generated {count} resources", file=sys.stderr)

    # Generate action resources
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
    action_count = 0
    generated_actions = []

    # Skip filesystem.put - it needs special HTTP multipart handling
    skip_actions = {"filesystem.put"}

    for method_name, method_spec in methods.items():
        if method_name in skip_actions:
            continue

        # Skip CRUD methods
        if any(
            method_name.endswith(suffix)
            for suffix in [".create", ".update", ".delete", ".query", ".get_instance"]
        ):
            continue

        # Check if it's an action (has job flag or action-like name)
        is_job = method_spec.get("job", False)
        has_action_name = any(
            keyword in method_name.split(".")[-1] for keyword in action_keywords
        )

        if is_job or has_action_name:
            code = generate_action_resource(method_name, method_spec, not_generated)
            if code:
                filename = f"action_{method_name.replace('.', '_')}_generated.go"
                (output_dir / filename).write_text(code)
                generated_actions.append(method_name)
                action_count += 1

                # Generate documentation
                accepts = method_spec.get("accepts", [])
                if accepts:
                    properties = {}
                    for param in accepts:
                        param_name = param.get("_name_", "")
                        if param_name:
                            properties[param_name] = param

                    description = (
                        method_spec.get("description")
                        or f"Execute {method_name} action"
                    )
                    description = description.split("\n")[0][:200]
                    generate_action_docs(method_name, properties, description)

    print(f"✅ Generated {action_count} action resources", file=sys.stderr)

    # Generate data sources
    datasource_candidates = [
        "vm",
        "pool",
        "pool.dataset",
        "disk",
        "user",
        "group",
        "interface",
        "service",
    ]
    datasource_dir = Path("internal/provider")
    ds_count = 0
    generated_datasources = []

    for base_name in datasource_candidates:
        if f"{base_name}.get_instance" not in methods:
            continue
        code = generate_datasource(base_name, methods, not_generated)
        if code:
            filename = f"datasource_{base_name.replace('.', '_')}_generated.go"
            (datasource_dir / filename).write_text(code)
            generated_datasources.append(base_name)
            ds_count += 1

            # Generate documentation
            get_spec = methods.get(f"{base_name}.get_instance", {})
            returns = get_spec.get("returns", [])
            if returns:
                schema = returns[0] if isinstance(returns, list) else returns
                properties = schema.get("properties", {})
                description = (
                    get_spec.get("description") or f"Retrieves TrueNAS {base_name} data"
                )
                description = description.split("\n")[0][:200]
                generate_datasource_docs(base_name, properties, description)

    print(f"✅ Generated {ds_count} data sources", file=sys.stderr)

    # Generate query data sources
    query_candidates = [
        "vm",
        "pool",
        "pool.dataset",
        "disk",
        "user",
        "group",
        "interface",
        "service",
    ]
    query_dir = Path("internal/provider")
    query_count = 0
    generated_query_datasources = []

    for base_name in query_candidates:
        if f"{base_name}.query" not in methods:
            continue
        code = generate_query_datasource(base_name, methods, not_generated)
        if code:
            filename = f"datasource_{base_name.replace('.', '_')}s_generated.go"
            (query_dir / filename).write_text(code)
            generated_query_datasources.append(base_name + "s")
            query_count += 1

            # Generate documentation
            query_spec = methods.get(f"{base_name}.query", {})
            returns = query_spec.get("returns", [])
            if returns:
                schema = returns[0] if isinstance(returns, list) else returns
                items_schema = schema.get("items", {})
                if isinstance(items_schema, list):
                    items_schema = items_schema[0] if items_schema else {}
                properties = items_schema.get("properties", {})
                # Filter out List types
                filtered_properties = {
                    k: v for k, v in properties.items() if get_tf_type(v) != "List"
                }
                description = (
                    query_spec.get("description") or f"Query {base_name} resources"
                )
                description = description.split("\n")[0][:200]
                generate_query_datasource_docs(
                    base_name, filtered_properties, description
                )

    print(f"✅ Generated {query_count} query data sources", file=sys.stderr)

    # Generate provider.go with all generated resources and actions
    generate_provider(
        generated_resources,
        generated_datasources + generated_query_datasources,
        generated_actions,
    )

    # filesystem.put is created manually
    skip_manual = ["filesystem.put"]

    print("\nNot Generating the following API methods:")
    for keyname in not_generated.keys():
        if keyname in skip_manual:
            continue
        print(keyname)


if __name__ == "__main__":
    main()
