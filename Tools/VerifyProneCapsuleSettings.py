"""PIE-only scenario probes. UObject references stay local so PIE teardown remains safe."""
import json
from pathlib import Path
import unreal

SAMPLES = []
BASELINE = {}
REPORT = Path(unreal.Paths.project_saved_dir()) / 'VibeUE/ProneCapsuleSettings-20261015/runtime-measurements.json'


def components():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    assert pawn is not None, 'Player pawn is not ready'
    mover = pawn.get_component_by_class(unreal.CharacterMoverComponent)
    assert mover is not None, 'Player has no CharacterMover'
    return pawn, mover, mover.get_updated_component()


def sample(name, stance, component_height=None, physics_height=None):
    pawn, mover, capsule = components()
    axis = unreal.ProneCapsuleUtils.get_physics_capsule_axis(capsule)
    rotation = capsule.get_world_rotation()
    entry = dict(name=name, prone=mover.is_prone(), crouch=mover.is_crouching(),
                 component_half_height=capsule.get_unscaled_capsule_half_height(),
                 radius=capsule.get_unscaled_capsule_radius(),
                 query_half_height=unreal.ProneCapsuleUtils.get_collision_half_height(capsule),
                 physics_half_height=unreal.ProneCapsuleUtils.get_physics_capsule_half_height(capsule),
                 physics_axis=[axis.x, axis.y, axis.z], root_pitch=rotation.pitch, root_roll=rotation.roll)
    SAMPLES.append(entry)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(SAMPLES, indent=2), encoding='utf-8')
    print('MEASURED:', json.dumps(entry))
    if name == 'standing-baseline':
        BASELINE.update(entry)
    expected_component = component_height if component_height is not None else BASELINE['component_half_height']
    expected_physics = physics_height if physics_height is not None else expected_component
    assert abs(entry['component_half_height'] - expected_component) < 0.05, entry
    assert abs(entry['physics_half_height'] - expected_physics) < 0.05, entry
    assert abs(entry['query_half_height'] - expected_physics) < 0.05, entry
    assert abs(rotation.pitch) < 0.05 and abs(rotation.roll) < 0.05, entry
    assert entry['prone'] == (stance == 'prone') and entry['crouch'] == (stance == 'crouch'), entry
    if stance == 'prone':
        assert abs(axis.z) < 0.05, entry
    else:
        assert abs(axis.z - 1) < 0.05, entry
    return True


def request(stance, component_height=None, physics_height=None):
    pawn, mover, capsule = components()
    settings = mover.find_shared_settings_mutable_bp(unreal.StanceSettings)
    if component_height is not None:
        settings.set_editor_property('prone_capsule_half_height', component_height)
    if physics_height is not None:
        settings.set_editor_property('prone_half_height', physics_height)
    if stance == 'prone':
        mover.prone()
    elif stance == 'crouch':
        mover.crouch()
    else:
        mover.un_prone()
        mover.un_crouch()
    print('MODIFIED: PIE stance', stance, 'component half height', component_height, 'physics half height', physics_height)
    return True


def scenario():
    def check(expression):
        return dict(action='python_assert', expression='prone_capsule_check.' + expression, expected='True')

    def wait(seconds=0.7):
        return dict(action='wait', seconds=seconds)

    return dict(name='independent-prone-component-and-physics-half-heights', steps=[
        dict(action='start_pie'), dict(action='wait_for_pie', timeout_seconds=30), wait(1.5),
        check("sample('standing-baseline','standing')"),
        dict(action='console_command', command='mover.debug.DrawProneCapsule 1'),
        check("request('prone')"), wait(),
        check("sample('prone-default','prone',42,72)"),
        dict(action='capture_game', name='vertical-component-horizontal-physics'), wait(15),
        check("request('standing')"), wait(), check("sample('standing-restored','standing')"),
        check("request('prone',50,72)"), wait(), check("sample('component-only-change','prone',50,72)"),
        check("request('standing')"), wait(),
        check("request('prone',50,84)"), wait(), check("sample('physics-only-change','prone',50,84)"),
        check("request('crouch')"), wait(), check("sample('crouch-restored','crouch',60,60)"),
        check("request('standing')"), wait(), check("sample('final-standing','standing')"),
        dict(action='console_command', command='mover.debug.DrawProneCapsule 0')
    ], teardown=dict(stop_pie=True))
