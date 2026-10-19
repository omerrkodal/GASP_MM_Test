import unreal
import json
from pathlib import Path
import vibeue

ABP = '/Game/Blueprints/SandboxCharacter_Mover_ABP'
GRAPH = 'AnimGraph'
SHOULDERS = '2B93254342C079216A814D8EFF1630A2'
AIM = '8786D82B41B679C8E3879B8056BEC111'
TOGGLE = '0D0D7DE14F8EF9B01997488B035A7D7B'
ROOT = Path(unreal.Paths.project_saved_dir()) / 'VibeUE' / 'CrawlPistolClavicles'
ROOT.mkdir(parents=True, exist_ok=True)
BS = unreal.BlueprintService
AG = unreal.AnimGraphService


def edges():
    return sorted((c.source_node_id, c.source_pin_name, c.target_node_id, c.target_pin_name)
                  for c in BS.get_connections(ABP, GRAPH))


def filters(node):
    return [[(str(f.get_editor_property('bone_name')), f.get_editor_property('blend_depth'))
             for f in layer.get_editor_property('branch_filters')]
            for layer in node.get_editor_property('node').get_editor_property('layer_setup')]


def configure(node, bones, weight):
    node.modify()
    settings = node.get_editor_property('node')
    layer = unreal.InputBlendPose()
    branch_filters = []
    for bone in bones:
        branch = unreal.BranchFilter()
        branch.set_editor_property('bone_name', bone)
        branch.set_editor_property('blend_depth', 1)
        branch_filters.append(branch)
    layer.set_editor_property('branch_filters', branch_filters)
    settings.set_editor_property('layer_setup', [layer])
    settings.set_editor_property('blend_weights', [weight])
    settings.set_editor_property('mesh_space_rotation_blend', True)
    node.set_editor_property('node', settings)
    print('MODIFIED:', node.get_path_name(), bones, weight)


def apply():
    state_file = ROOT / 'state.json'
    assert not state_file.exists(), 'Already applied or partially applied; inspect state.json before rerunning.'
    bp = unreal.load_asset(ABP)
    shoulder_node = unreal.find_object(None, ABP + '.SandboxCharacter_Mover_ABP:AnimGraph.AnimGraphNode_LayeredBoneBlend_3')
    assert shoulder_node and filters(shoulder_node) == [[('clavicle_r', 1), ('clavicle_l', 0)]]
    before = edges()
    assert (SHOULDERS, 'Pose', TOGGLE, 'BlendPose_0') in before
    run = json.loads(unreal.WorkflowService.start_run('CrawlPistolClavicleBlend', json.dumps({'abp': ABP, 'clavicleAimWeight': 0.35, 'armAimWeight': 1.0})))
    print('RUN_START:', json.dumps(run))
    run_id = run.get('runId') or run.get('run_id') or run.get('id')
    assert run_id, 'Inspect start_run return before mutation'
    old_settings = shoulder_node.get_editor_property('node')
    state = {'abp': ABP, 'run_id': run_id, 'original_filters': filters(shoulder_node),
             'original_weights': list(old_settings.get_editor_property('blend_weights')),
             'original_mesh_space_rotation_blend': old_settings.get_editor_property('mesh_space_rotation_blend'),
             'connections_before': before}
    state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    names_before = {o.get_path_name() for o in unreal.ObjectIterator(unreal.AnimGraphNode_LayeredBoneBlend)}
    arm_id = AG.add_layered_blend(ABP, GRAPH, 4000, 16)
    assert arm_id
    new_nodes = [o for o in unreal.ObjectIterator(unreal.AnimGraphNode_LayeredBoneBlend)
                 if o.get_path_name() not in names_before and o.get_path_name().startswith(ABP + '.')]
    assert len(new_nodes) == 1
    arm_node = new_nodes[0]
    state.update(arm_node_id=arm_id, arm_node_path=arm_node.get_path_name())
    state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    print('CREATED:', arm_node.get_path_name(), arm_id)
    configure(shoulder_node, ['clavicle_l', 'clavicle_r'], 0.35)
    configure(arm_node, ['upperarm_l', 'upperarm_r'], 1.0)
    assert BS.set_node_pin_value(ABP, GRAPH, SHOULDERS, 'BlendWeights_0', '0.35')
    assert BS.set_node_pin_value(ABP, GRAPH, arm_id, 'BlendWeights_0', '1.0')
    assert AG.connect_anim_nodes(ABP, GRAPH, SHOULDERS, 'Pose', arm_id, 'BasePose')
    assert AG.connect_anim_nodes(ABP, GRAPH, AIM, 'Pose', arm_id, 'BlendPoses_0')
    assert BS.disconnect_pin(ABP, GRAPH, TOGGLE, 'BlendPose_0')
    assert AG.connect_anim_nodes(ABP, GRAPH, arm_id, 'Pose', TOGGLE, 'BlendPose_0')
    expected = set(before) - {(SHOULDERS, 'Pose', TOGGLE, 'BlendPose_0')}
    expected.update([(SHOULDERS, 'Pose', arm_id, 'BasePose'),
                     (AIM, 'Pose', arm_id, 'BlendPoses_0'),
                     (arm_id, 'Pose', TOGGLE, 'BlendPose_0')])
    assert set(edges()) == expected, 'Unexpected graph connection change'
    result = vibeue.exec_tool('editor_toolset.toolsets.blueprint.BlueprintTools', 'compile_blueprint',
                             {'blueprint': {'refPath': bp.get_path_name()}, 'warnings_as_errors': False})
    print('COMPILE:', result)
    assert filters(shoulder_node) == [[('clavicle_l', 1), ('clavicle_r', 1)]]
    assert filters(arm_node) == [[('upperarm_l', 1), ('upperarm_r', 1)]]
    assert abs(shoulder_node.get_editor_property('node').get_editor_property('blend_weights')[0] - 0.35) < 0.0001
    assert abs(arm_node.get_editor_property('node').get_editor_property('blend_weights')[0] - 1.0) < 0.0001
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)
    print('SAVED:', ABP)
    state.update(verified=True, compile_result=result, connections_after=edges())
    state_file.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')
    print('ARTIFACT:', unreal.WorkflowService.attach_run_artifact(run_id, str(state_file), 'file'))
    print('FOCUSED:', AG.focus_node(ABP, arm_id))
    print('VERIFIED: clavicles=0.35, upperarms and descendants=1.0; graph diff matches expected')


def finish_existing():
    state_file = ROOT / 'state.json'
    state = json.loads(state_file.read_text(encoding='utf-8'))
    arm_id = state['arm_node_id']
    expected = {tuple(e) for e in state['connections_before']} - {(SHOULDERS, 'Pose', TOGGLE, 'BlendPose_0')}
    expected.update([(SHOULDERS, 'Pose', arm_id, 'BasePose'),
                     (AIM, 'Pose', arm_id, 'BlendPoses_0'),
                     (arm_id, 'Pose', TOGGLE, 'BlendPose_0')])
    if set(edges()) != expected:
        assert set(edges()) == expected | {(SHOULDERS, 'Pose', TOGGLE, 'BlendPose_0')}
        assert BS.disconnect_pin(ABP, GRAPH, TOGGLE, 'BlendPose_0')
        assert AG.connect_anim_nodes(ABP, GRAPH, arm_id, 'Pose', TOGGLE, 'BlendPose_0')
        print('MODIFIED: replaced old direct toggle link with arm layer')
    assert set(edges()) == expected
    print('LAYOUT:', BS.auto_layout_selected_nodes(ABP, GRAPH,
          [SHOULDERS, arm_id, TOGGLE, '4E122C5B4DB554E65D88549408D0932C', 'B91B8C944754B09AE130389CCF6A55F4']))
    bp = unreal.load_asset(ABP)
    result = vibeue.exec_tool('editor_toolset.toolsets.blueprint.BlueprintTools', 'compile_blueprint',
                             {'blueprint': {'refPath': bp.get_path_name()}, 'warnings_as_errors': False})
    print('COMPILE:', result)
    for path, bones, weight in [
        (ABP + '.SandboxCharacter_Mover_ABP:AnimGraph.AnimGraphNode_LayeredBoneBlend_3', ['clavicle_l', 'clavicle_r'], 0.35),
        (state['arm_node_path'], ['upperarm_l', 'upperarm_r'], 1.0)]:
        obj = unreal.find_object(None, path)
        settings = obj.get_editor_property('node')
        assert filters(obj) == [[(b, 1) for b in bones]]
        assert abs(settings.get_editor_property('blend_weights')[0] - weight) < 0.0001
        assert settings.get_editor_property('mesh_space_rotation_blend')
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)
    print('SAVED:', ABP)
    state.update(verified=True, compile_result=result, connections_after=edges())
    state_file.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')
    print('ARTIFACT:', unreal.WorkflowService.attach_run_artifact(state['run_id'], str(state_file), 'file'))
    print('FOCUSED:', AG.focus_node(ABP, arm_id))
    print('VERIFIED: clavicles=0.35, upperarms and descendants=1.0; exact graph audit passed')


if (ROOT / 'state.json').exists():
    finish_existing()
else:
    apply()
