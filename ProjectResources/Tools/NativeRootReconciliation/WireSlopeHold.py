"""Run through Unreal Python AFTER rebuilding/reopening with the slope-hold C++ revision.

No Blueprint mutation occurs until the required native getter is loaded.
"""
import unreal
import json
from pathlib import Path


def wire():
    if not hasattr(unreal.CharacterMoverComponent, 'get_offset_root_reconciliation_radius_hold'):
        print('REBUILD REQUIRED: slope-hold native getter is not loaded; no Blueprint changes applied.')
        return
    bp = '/Game/Blueprints/SandboxCharacter_Mover_ABP'
    graph = 'EventGraph'
    folder = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/NativeRootReconciliation/slope-hold-v2'
    with (folder.parent / 'abp-node-refs.json').open() as f:
        original = json.load(f)
    if unreal.BlueprintService.function_call_exists(bp, graph, 'GetOffsetRootReconciliationRadiusHold'):
        print('EXISTS: slope-hold bridge; no duplicate created')
        return
    asset = unreal.EditorAssetLibrary.load_asset(bp)
    variable = 'RootReconcileRadiusHold'
    if not any(v.variable_name == variable for v in unreal.BlueprintService.list_variables(bp)):
        import vibeue
        vibeue.exec_tool('editor_toolset.toolsets.blueprint.BlueprintTools', 'add_variable',
            {'blueprint': {'refPath': bp + '.SandboxCharacter_Mover_ABP'},
             'name': variable, 'type_name': 'float'})
        print('ADDED:', variable)
        unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    before = unreal.BlueprintService.get_connections(bp, graph)
    next_links = [c for c in before if c.source_node_id == original['reconcile'] and c.source_pin_name == 'then']
    assert len(next_links) == 1
    next_node, next_pin = next_links[0].target_node_id, next_links[0].target_pin_name
    nodes = [
        {'ref': 'sourceRadius', 'type': 'variable_get', 'params': {'variable': 'RootRadiusCurveOutput'}},
        {'ref': 'nativeHold', 'type': 'function_call', 'params': {'class': 'CharacterMoverComponent', 'function': 'GetOffsetRootReconciliationRadiusHold'}},
        {'ref': 'copyHold', 'type': 'variable_set', 'params': {'variable': variable}},
        {'ref': 'resetHold', 'type': 'variable_set', 'params': {'variable': variable}},
    ]
    result = unreal.BlueprintService.build_graph(bp, graph, nodes,
        [{'from_': original['mover'] + '.Character Mover', 'to': 'nativeHold.self'},
         {'from_': 'nativeHold.ReturnValue', 'to': 'copyHold.' + variable}],
        [{'node_ref': 'resetHold', 'pin_name': variable, 'value': '0'}], False, False)
    assert result.success, list(result.errors)
    refs = dict(result.ref_to_node_id)
    # Replace the raw-curve input with the existing curve-backed one-second hold.
    unreal.BlueprintService.disconnect_pin(bp, graph, original['reconcile'], 'CurveValue')
    unreal.BlueprintService.disconnect_pin(bp, graph, original['reconcile'], 'then')
    unreal.BlueprintService.disconnect_pin(bp, graph, original['gate'], 'else')
    links = [
        {'from_': refs['sourceRadius'] + '.RootRadiusCurveOutput', 'to': original['reconcile'] + '.CurveValue'},
        {'from_': original['reconcile'] + '.then', 'to': refs['copyHold'] + '.execute'},
        {'from_': refs['copyHold'] + '.then', 'to': next_node + '.' + next_pin},
        {'from_': original['gate'] + '.else', 'to': refs['resetHold'] + '.execute'},
        {'from_': refs['resetHold'] + '.then', 'to': next_node + '.' + next_pin},
    ]
    result = unreal.BlueprintService.build_graph(bp, graph, [], links, [], False, False)
    assert result.success, list(result.errors)
    radius_graph = 'Get_OffsetRootTranslationRadius'
    connections = unreal.BlueprintService.get_connections(bp, radius_graph)
    old = [c for c in connections if c.source_pin_name == 'RootRadiusCurveOutput' and c.target_pin_name == 'ReturnValue']
    assert len(old) == 1
    old = old[0]
    result = unreal.BlueprintService.build_graph(bp, radius_graph,
        [{'ref': 'hold', 'type': 'variable_get', 'params': {'variable': variable}},
         {'ref': 'safeRadius', 'type': 'function_call', 'params': {'class': 'KismetMathLibrary', 'function': 'FMax'}}],
        [{'from_': old.source_node_id + '.RootRadiusCurveOutput', 'to': 'safeRadius.A'},
         {'from_': 'hold.' + variable, 'to': 'safeRadius.B'}], [], False, False)
    assert result.success, list(result.errors)
    radius_refs = dict(result.ref_to_node_id)
    # Preserve IDs before compilation so an interrupted integration can be inspected.
    (folder / 'abp-slope-hold-refs.json').write_text(json.dumps({'event': refs, 'getter': radius_refs}, indent=2))
    # Repair the known pre-existing duplicate execution edge, retaining the valid-Mover guard.
    reset_id = '26D84EC44BDFBDCC5E871C9A28C7631A'
    reset_links = [c for c in unreal.BlueprintService.get_connections(bp, graph)
                   if c.source_node_id == reset_id and c.source_pin_name == 'then']
    if len(reset_links) == 2 and {c.target_node_id for c in reset_links} == {original['gate'], original['reconcile']}:
        assert all(c.target_pin_name == 'execute' for c in reset_links)
        unreal.BlueprintService.disconnect_pin(bp, graph, reset_id, 'then')
        repair = unreal.BlueprintService.build_graph(bp, graph, [],
            [{'from_': reset_id + '.then', 'to': original['gate'] + '.execute'}], [], False, False)
        assert repair.success, list(repair.errors)
        print('MODIFIED: removed duplicate direct reconciliation execution edge')
    unreal.BlueprintService.disconnect_pin(bp, radius_graph, old.target_node_id, 'ReturnValue')
    result = unreal.BlueprintService.build_graph(bp, radius_graph, [],
        [{'from_': radius_refs['safeRadius'] + '.ReturnValue', 'to': old.target_node_id + '.ReturnValue'}], [], False, True)
    assert result.success, list(result.errors)
    # Layout only added nodes. Original graph positions are preserved.
    for name, ids in [(graph, list(refs.values())), (radius_graph, list(radius_refs.values()))]:
        existing = unreal.BlueprintService.get_nodes_in_graph(bp, name, 0, '', False)
        bottom = max(n.pos_y for n in existing if n.node_id not in ids) + 450
        unreal.BlueprintService.auto_layout_selected_nodes(bp, name, ids)
        added = [n for n in unreal.BlueprintService.get_nodes_in_graph(bp, name, 0, '', False) if n.node_id in ids]
        top = min(n.pos_y for n in added)
        for n in added:
            unreal.BlueprintService.set_node_position(bp, name, n.node_id, n.pos_x, n.pos_y - top + bottom)
        unreal.BlueprintService.add_comment_around_nodes(bp, name,
            'Slope-safe native catch-up radius hold; no timer mutation in pure getter', ids)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    print('COMPILE:', asset.get_editor_property('status'))
    assert unreal.EditorAssetLibrary.save_asset(bp, False)
    assert unreal.BlueprintService.function_call_exists(bp, graph, 'GetOffsetRootReconciliationRadiusHold')
    (folder / 'abp-slope-hold-refs.json').write_text(json.dumps({'event': refs, 'getter': radius_refs}, indent=2))
    print('MODIFIED:', bp)
    print('Radius getter now returns max(curve-backed radius, copied native hold). Gameplay testing remains with user.')


wire()
