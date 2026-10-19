import unreal
import json
from pathlib import Path

ASSET = '/Game/Blueprints/ControlRigs/CR_Prone'
NAME = 'Spine FBIK Test'
rig = unreal.EditorAssetLibrary.load_asset(ASSET)
editor = rig.get_editor_asset()
main = editor.get_model()
library = editor.get_local_function_library()
assert not any(n.get_name() == NAME for n in library.get_nodes()), 'Function already exists'
source = next(g for g in library.get_contained_graphs(True) if g.get_outer().get_name() == 'Spine IK Test')
source_controller = editor.get_controller(source)
copy_names = [n.get_name() for n in source.get_nodes() if n.get_name() not in ['Entry', 'Return', 'SpineCCD']]
source_text = source_controller.export_nodes_to_text(copy_names, False)
source_prefix = source.get_path_name() + '.'
source_links = [(l.get_source_pin().get_path_name().removeprefix(source_prefix),
                 l.get_target_pin().get_path_name().removeprefix(source_prefix)) for l in source.get_links()]
inherited_links = [(a, b) for a, b in source_links
                   if a.split('.')[0] in copy_names and b.split('.')[0] in copy_names]
folder = Path(unreal.Paths.project_saved_dir()) / 'VibeUE' / 'ProneSpineFBIKTest'
folder.mkdir(parents=True, exist_ok=True)
mc = editor.get_controller(main)
(folder / 'main-before.txt').write_text(mc.export_nodes_to_text([n.get_name() for n in main.get_nodes()], False))
(folder / 'shared-target-before.txt').write_text(source_text)
run = json.loads(unreal.WorkflowService.start_run(NAME, json.dumps({'asset': ASSET, 'gameplayTesting': 'user-owned'})))['runId']
(folder / 'run-id.txt').write_text(run)
lc = editor.get_controller(library)
assert lc.open_undo_bracket('Add separate spine FBIK test')
try:
    fn = lc.add_function_to_library(NAME, True)
    assert fn
    print('CREATED:', ASSET, NAME)
    graph = fn.get_contained_graph()
    c = editor.get_controller(graph)
    assert c.add_exposed_pin('Alpha', unreal.RigVMPinDirection.INPUT, 'float', '', '1.0')
    assert c.add_exposed_pin('RotationStiffness', unreal.RigVMPinDirection.INPUT, 'float', '', '0.5')
    imported = [str(n) for n in c.import_nodes_from_text(source_text)]
    assert set(imported) == set(copy_names), imported
    def unit(name, path, x, y, defaults=None):
        n = c.add_unit_node_from_struct_path(path, 'Execute', unreal.Vector2D(x, y), name)
        assert n, name
        for pin, value in (defaults or {}).items():
            assert c.set_pin_default_value(name + '.' + pin, value), (name, pin)
        return n
    unit('Enabled', '/Script/RigVM.RigVMFunction_MathFloatGreater', 1750, -250, {'B': '0.0001'})
    unit('Stiffness', '/Script/RigVM.RigVMFunction_MathFloatClamp', 1750, 50,
         {'Minimum': '0.0', 'Maximum': '1.0'})
    gate = c.add_branch_node(unreal.Vector2D(2000, -250), 'ContactGate')
    assert gate
    gate_pins = [p.get_name() for p in gate.get_pins()]
    assert all(p in gate_pins for p in ['ExecuteContext', 'Condition', 'True', 'Completed']), gate_pins
    unit('SpineFBIK', '/Script/PBIK.RigUnit_PBIK', 2300, 350, {
        'Root': 'spine_01',
        'Effectors': '((Bone="spine_05",PositionAlpha=1.0,RotationAlpha=1.0,StrengthAlpha=1.0,ChainDepth=4,PullChainAlpha=0.0,PinRotation=1.0))',
        'BoneSettings': '(' + ','.join('(Bone="spine_%02d",RotationStiffness=0.5,PositionStiffness=0.0,bUsePreferredAngles=False)' % i for i in range(2, 6)) + ')',
        'Settings.Iterations': '20',
        'Settings.bAllowStretch': 'False',
        'Settings.RootBehavior': 'PinToInput',
        'Settings.GlobalPullChainAlpha': '0.0'})
    added_links = []
    def link(a, b):
        assert c.add_link(a, b), (a, b)
        added_links.append((a, b))
    link('Entry.Alpha', 'ContactAlpha.IfTrue')
    link('ClampAlpha.Result', 'Enabled.A')
    link('Enabled.Result', 'ContactGate.Condition')
    link('Entry.RotationStiffness', 'Stiffness.Value')
    for i in range(4):
        link('Stiffness.Result', 'SpineFBIK.BoneSettings.%d.RotationStiffness' % i)
    link('ReachableChestTarget.Result', 'SpineFBIK.Effectors.0.Transform.Translation')
    link('Chest.Transform.Rotation', 'SpineFBIK.Effectors.0.Transform.Rotation')
    link('Chest.Transform.Scale3D', 'SpineFBIK.Effectors.0.Transform.Scale3D')
    link('ClampAlpha.Result', 'SpineFBIK.Effectors.0.PositionAlpha')
    if any(l.get_source_pin().get_path_name().endswith('.Entry.ExecuteContext') and
           l.get_target_pin().get_path_name().endswith('.Return.ExecuteContext') for l in graph.get_links()):
        assert c.break_link('Entry.ExecuteContext', 'Return.ExecuteContext')
    link('Entry.ExecuteContext', 'ContactGate.ExecuteContext')
    link('ContactGate.True', 'SpineFBIK.ExecutePin')
    link('ContactGate.Completed', 'Return.ExecuteContext')
    call = mc.add_function_reference_node(fn, unreal.Vector2D(3460, 1450), NAME)
    assert call
    call_name = call.get_name()
    assert mc.set_pin_default_value(call_name + '.Alpha', '1.0')
    assert mc.set_pin_default_value(call_name + '.RotationStiffness', '0.5')
    assert mc.break_link('Set Transform.ExecutePin', 'Spine IK Test.ExecuteContext')
    assert mc.break_link('Spine IK Test.ExecuteContext', 'Foot IK Test.ExecuteContext')
    assert mc.add_link('Set Transform.ExecutePin', call_name + '.ExecuteContext')
    assert mc.add_link(call_name + '.ExecuteContext', 'Foot IK Test.ExecuteContext')
    assert lc.close_undo_bracket()
except Exception:
    lc.cancel_undo_bracket()
    unreal.WorkflowService.finish_run(run, 'partial', 'FBIK function creation failed; edit undo bracket cancelled')
    raise
print('MODIFIED:', ASSET, 'root translation -> Spine FBIK Test -> Foot IK Test; CCD call disconnected')
log = Path(unreal.Paths.project_log_dir()) / 'GASP_MM_Test.log'
offset = log.stat().st_size
editor.recompile_vm()
assert unreal.EditorAssetLibrary.save_loaded_asset(rig, False)
prefix = graph.get_path_name() + '.'
links = [(l.get_source_pin().get_path_name().removeprefix(prefix), l.get_target_pin().get_path_name().removeprefix(prefix)) for l in graph.get_links()]
assert all(pair in links for pair in inherited_links + added_links)
mp = main.get_path_name() + '.'
main_links = [(l.get_source_pin().get_path_name().removeprefix(mp), l.get_target_pin().get_path_name().removeprefix(mp)) for l in main.get_links()]
assert ('Set Transform.ExecutePin', call_name + '.ExecuteContext') in main_links
assert (call_name + '.ExecuteContext', 'Foot IK Test.ExecuteContext') in main_links
assert not any(a.startswith('Spine IK Test.ExecuteContext') or b.startswith('Spine IK Test.ExecuteContext') for a, b in main_links)
solver = next(n for n in graph.get_nodes() if n.get_name() == 'SpineFBIK')
settings = next(p.get_default_value() for p in solver.get_pins() if p.get_name() == 'Settings')
assert 'PinToInput' in settings and 'bAllowStretch=False' in settings
with log.open('rb') as stream:
    stream.seek(offset)
    compile_log = stream.read().decode('utf-8', 'replace')
errors = [line for line in compile_log.splitlines() if any(t in line for t in ['LogRigVM: Error', 'LogControlRig: Error', 'LogRigVMCompiler: Error', 'LogPBIKSolver: Error'])]
report = {'asset': ASSET, 'function': NAME, 'root': 'spine_01', 'effector': 'spine_05',
          'alpha': 1, 'rotationStiffness': 0.5, 'iterations': 20, 'settings': settings,
          'copiedTargetNodes': len(imported), 'linksAudited': len(inherited_links + added_links),
          'compiledAndSaved': True, 'compileErrors': errors, 'gameplayVerified': False,
          'rollback': {'removeCreatedFunction': NAME, 'removeCreatedCall': call_name,
                       'removeLinks': [['Set Transform.ExecutePin', call_name + '.ExecuteContext'], [call_name + '.ExecuteContext', 'Foot IK Test.ExecuteContext']],
                       'restoreLinks': [['Set Transform.ExecutePin', 'Spine IK Test.ExecuteContext'], ['Spine IK Test.ExecuteContext', 'Foot IK Test.ExecuteContext']]}}
(folder / 'audit.json').write_text(json.dumps(report, indent=2))
(folder / 'compile-log.txt').write_text(compile_log)
(folder / 'function.txt').write_text(c.export_nodes_to_text([n.get_name() for n in graph.get_nodes()], False))
(folder / 'main-after.txt').write_text(mc.export_nodes_to_text([n.get_name() for n in main.get_nodes()], False))
for name in ['audit.json', 'main-before.txt', 'main-after.txt', 'function.txt', 'compile-log.txt', 'shared-target-before.txt']:
    unreal.WorkflowService.attach_run_artifact(run, str(folder / name), 'file')
unreal.WorkflowService.finish_run(run, 'partial' if errors else 'succeeded',
    'Created separate spine-only FBIK test and switched execution from CCD. Root pinned, stretch disabled, pose-derived target reused, contact/zero-alpha bypass enabled. VM compiled/saved and links/settings audited. Gameplay testing left to user.')
print('AUDIT', json.dumps(report))
