"""Run through Unreal's Python API after loading the compiled native Mover extension."""
import unreal
import json
from pathlib import Path


def wire():
    bp = '/Game/Blueprints/SandboxCharacter_Mover_ABP'
    graph = 'EventGraph'
    folder = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/NativeRootReconciliation'
    if unreal.BlueprintService.function_call_exists(bp, graph, 'ReconcileOffsetRootOnStop'):
        print('EXISTS: native reconciliation call; no duplicate created')
        return
    before = unreal.BlueprintService.get_connections(bp, graph)
    reset = '26D84EC44BDFBDCC5E871C9A28C7631A'
    debug = 'D683138F476BA5015E5705881963570E'
    old = [c for c in before if c.source_node_id == reset and c.source_pin_name == 'then']
    assert len(old) == 1 and old[0].target_node_id == debug, 'Post-evaluation flow changed; inspect before wiring'
    specs = [
        ('mover', 'variable_get', {'variable': 'Character Mover'}),
        ('root', 'variable_get', {'variable': 'RootTransform'}),
        ('enabled', 'variable_get', {'variable': 'OffsetRootBoneEnabled'}),
        ('valid', 'function_call', {'class': 'KismetSystemLibrary', 'function': 'IsValid'}),
        ('gate', 'branch', {}),
        ('location', 'function_call', {'class': 'KismetMathLibrary', 'function': 'BreakTransform'}),
        ('curve', 'function_call', {'class': 'AnimInstance', 'function': 'GetCurveValue'}),
        ('mode', 'function_call', {'class': bp + '.SandboxCharacter_Mover_ABP_C', 'function': 'Get_OffsetRootTranslationMode'}),
        ('accumulate', 'function_call', {'class': 'KismetMathLibrary', 'function': 'EqualEqual_ByteByte'}),
        ('allowed', 'function_call', {'class': 'KismetMathLibrary', 'function': 'BooleanAND'}),
        ('reconcile', 'function_call', {'class': 'CharacterMoverComponent', 'function': 'ReconcileOffsetRootOnStop'}),
    ]
    nodes = [{'ref': ref, 'type': typ, 'params': params} for ref, typ, params in specs]
    data = [
        ('mover.Character Mover', 'valid.Object'), ('valid.ReturnValue', 'gate.Condition'),
        ('mover.Character Mover', 'reconcile.self'), ('root.RootTransform', 'location.InTransform'),
        ('location.Location', 'reconcile.AnimatedRootWorldLocation'),
        ('curve.ReturnValue', 'reconcile.CurveValue'), ('mode.ReturnValue', 'accumulate.A'),
        ('accumulate.ReturnValue', 'allowed.A'), ('enabled.OffsetRootBoneEnabled', 'allowed.B'),
        ('allowed.ReturnValue', 'reconcile.bRootIsAccumulating'),
    ]
    result = unreal.BlueprintService.build_graph(bp, graph, nodes,
        [{'from_': a, 'to': b} for a, b in data],
        [{'node_ref': 'curve', 'pin_name': 'CurveName', 'value': 'Set_OffsetRootTranslationRadius'},
         {'node_ref': 'accumulate', 'pin_name': 'B', 'value': '0'}], False, False)
    print('CREATE:', result.success, list(result.errors), list(result.warnings))
    assert result.success, 'New nodes are unexecuted; existing event flow is unchanged'
    refs = dict(result.ref_to_node_id)
    with (folder / 'abp-node-refs.json').open('w') as output:
        json.dump(refs, output, indent=2)

    assert unreal.BlueprintService.disconnect_pin(bp, graph, reset, 'then')
    execution = [
        {'from_': reset + '.then', 'to': refs['gate'] + '.execute'},
        {'from_': refs['gate'] + '.then', 'to': refs['reconcile'] + '.execute'},
        {'from_': refs['gate'] + '.else', 'to': debug + '.execute'},
        {'from_': refs['reconcile'] + '.then', 'to': debug + '.execute'},
    ]
    result = unreal.BlueprintService.build_graph(bp, graph, [], execution, [], False, True)
    print('CONNECT:', result.success, list(result.errors), list(result.warnings))
    assert result.success
    ids = list(refs.values())
    unreal.BlueprintService.auto_layout_selected_nodes(bp, graph, ids)
    all_nodes = unreal.BlueprintService.get_nodes_in_graph(bp, graph, 0, '', False)
    original = [n for n in all_nodes if n.node_id not in ids]
    new = [n for n in all_nodes if n.node_id in ids]
    minimum_x = min(n.pos_x for n in new)
    minimum_y = min(n.pos_y for n in new)
    event = next(n for n in original if n.node_id == 'A77AE76D4892D26F14F2139FC1476E4A')
    destination_y = max(n.pos_y for n in original) + 600
    for node in new:
        unreal.BlueprintService.set_node_position(bp, graph, node.node_id,
            node.pos_x - minimum_x + event.pos_x, node.pos_y - minimum_y + destination_y)
    comment = unreal.BlueprintService.add_comment_around_nodes(bp, graph,
        'Native capsule/root alignment on stop - game-thread Post Evaluate; raw curve; Accumulate only', ids)
    asset = unreal.EditorAssetLibrary.load_asset(bp)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    print('COMPILE:', asset.get_editor_property('status'))
    assert unreal.EditorAssetLibrary.save_asset(bp, False)
    print('MODIFIED:', bp)
    after = unreal.BlueprintService.get_connections(bp, graph)
    original_connections = {(c.source_node_id, c.source_pin_name, c.target_node_id, c.target_pin_name) for c in before}
    original_connections.remove((reset, 'then', debug, 'execute'))
    final_connections = {(c.source_node_id, c.source_pin_name, c.target_node_id, c.target_pin_name) for c in after}
    assert original_connections <= final_connections, 'An unrelated original link changed'
    print('VERIFIED: original links preserved; game-thread native call connected; gameplay testing left to user')
    print('COMMENT:', comment)
    unreal.AnimGraphService.focus_node(bp, comment or refs['reconcile'])


wire()
