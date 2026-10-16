import unreal
import json
import math
import os

# Run through VibeUE execute_python_code inside the editor. Asset data stays in UE.
ASS = unreal.AnimSequenceService
BASE = '/Game/_GAME/Anims/Crawl'
LOOP = BASE + '/Loop/Crawl_Loop_B'
OUT = BASE + '/Stops'
FPS = 30
FRAMES = 60
DURATION = (FRAMES - 1) / FPS
BRAKE_START, BRAKE_END = 0.35, 1.15
BLEND_START, BLEND_END = 0.35, 1.55
TRAVEL_TIME = (BRAKE_START + BRAKE_END) / 2
REPORT_DIR = os.path.join(unreal.Paths.project_saved_dir(), 'VibeUE', 'BackwardCrawlStops')


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u*u*u*(10 + u*(-15 + 6*u))


def progress(t):
    if t <= BRAKE_START:
        return t
    u = min(1.0, (t - BRAKE_START) / (BRAKE_END - BRAKE_START))
    return BRAKE_START + (BRAKE_END - BRAKE_START)*(u - u**3 + 0.5*u**4)


def speed_weight(t):
    u = max(0.0, min(1.0, (t - BRAKE_START)/(BRAKE_END - BRAKE_START)))
    return 1 - u*u*(3 - 2*u)


def quat_blend(a, b, w):
    av, bv = [a.x, a.y, a.z, a.w], [b.x, b.y, b.z, b.w]
    dot = sum(x*y for x,y in zip(av,bv))
    if dot < 0:
        bv, dot = [-v for v in bv], -dot
    dot = min(1.0, dot)
    if dot > 0.9995:
        v = [(1-w)*x+w*y for x,y in zip(av,bv)]
    else:
        angle = math.acos(dot)
        sa, sb = math.sin((1-w)*angle)/math.sin(angle), math.sin(w*angle)/math.sin(angle)
        v = [sa*x+sb*y for x,y in zip(av,bv)]
    length = math.sqrt(sum(x*x for x in v))
    return unreal.Quat(*(x/length for x in v))


def pose(path, t, global_space=False):
    return {str(b.bone_name): b.transform for b in ASS.get_pose_at_time(path, t, global_space)}


def transform(position, rotation, scale):
    value = unreal.Transform()
    value.translation = position
    value.rotation = rotation
    value.scale3d = scale
    return value


def plan(side, loop_info, loop_poses):
    idle = BASE + '/Idle/Crawl_Idle_Loop_' + side
    target = pose(idle, 0, True)
    def score(f):
        p = loop_poses[f]
        return sum(((p[b].translation-p['root'].translation) -
                    (target[b].translation-target['root'].translation)).length_squared()*w
                   for b,w in [('hand_l',2),('hand_r',2),('foot_l',1),('foot_r',1),('pelvis',1)])
    candidates = range(math.ceil(TRAVEL_TIME*FPS), loop_info.frame_count-math.ceil(TRAVEL_TIME*FPS))
    end_frame = min(candidates, key=score)
    end_time = end_frame/FPS
    start_time = end_time + TRAVEL_TIME
    origin = pose(LOOP, start_time)['root'].translation
    idle_duration = ASS.get_animation_length(idle)
    samples, times, weights = [], [], []
    for f in range(FRAMES):
        t = f/FPS
        source_time = start_time-progress(t)
        a = pose(LOOP, source_time)
        # End at idle frame zero with its natural incoming breathing velocity.
        b = pose(idle, (idle_duration+t-DURATION) % idle_duration)
        w = smooth((t-BLEND_START)/(BLEND_END-BLEND_START))
        result = {}
        for bone, at in a.items():
            bt = b[bone]
            result[bone] = transform(at.translation*(1-w)+bt.translation*w,
                                     quat_blend(at.rotation,bt.rotation,w),
                                     at.scale3d*(1-w)+bt.scale3d*w)
        root = a['root']
        delta = root.translation-origin
        result['root'] = transform(unreal.Vector(delta.x,delta.y,0),root.rotation,root.scale3d)
        samples.append(result)
        times.append(source_time)
        weights.append(w)
    max_angle = 0.0
    for a,b in zip(samples,samples[1:]):
        for bone in a:
            qa,qb=a[bone].rotation,b[bone].rotation
            dot=abs(qa.x*qb.x+qa.y*qb.y+qa.z*qb.z+qa.w*qb.w)
            max_angle=max(max_angle,math.degrees(2*math.acos(min(1.0,dot))))
    assert max_angle < 35, ('discontinuous pose', side, max_angle)
    assert samples[-1]['root'].translation.y < -1, 'Expected backward root travel'
    tracks=[]
    for bone in samples[0]:
        keys=[unreal.AnimKeyframe(frame=f,time=f/FPS,position=p[bone].translation,
                                 rotation=p[bone].rotation,scale=p[bone].scale3d)
              for f,p in enumerate(samples)]
        tracks.append(unreal.BoneTrackData(bone_name=bone,keyframes=keys))
    return dict(side=side,idle=idle,start_time=start_time,end_time=end_time,
                samples=samples,times=times,weights=weights,tracks=tracks,max_angle=max_angle)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    outputs=[OUT+'/Crawl_Stop_B_'+s for s in ['Left','Right']]
    assert not any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in outputs), 'Outputs already exist; inspect instead of overwriting.'
    info=ASS.get_anim_sequence_info(LOOP)
    assert info.rate_scale < 0, 'Source no longer uses backward playback'
    profile=unreal.SkeletonService.create_skeleton_profile(info.skeleton_path)
    assert profile.bone_count == 93
    globals_=[pose(LOOP,f/FPS,True) for f in range(info.frame_count)]
    plans=[plan(side,info,globals_) for side in ['Left','Right']]
    print('PREVIEW_VALIDATED:',[(p['side'],p['start_time'],p['end_time'],p['max_angle']) for p in plans])
    run=json.loads(unreal.WorkflowService.start_run('Create backward crawl stop pair',json.dumps({'source':LOOP,'outputs':outputs,'method':'phase-matched reversed loop, smooth deceleration, local quaternion blend to matching idle'})))['runId']
    report={'run':run,'outputs':[],'method':'Reverse loop sampling with root deceleration and quintic local-space idle blending; no gameplay wiring.'}
    try:
        for p in plans:
            name='Crawl_Stop_B_'+p['side']
            path=ASS.create_anim_sequence(info.skeleton_path,name,OUT,DURATION,FPS,p['tracks'])
            assert path, name+' creation failed'
            print('CREATED:',path)
            assert ASS.set_enable_root_motion(path,True)
            assert ASS.set_root_motion_root_lock(path,'RefPose')
            assert ASS.set_rate_scale(path,1)
            # Use source curve names and values; no copied forward Foley events.
            curve_names=set(str(c.curve_name) for c in ASS.list_curves(LOOP)) | set(str(c.curve_name) for c in ASS.list_curves(p['idle']))
            idle_names=set(str(c.curve_name) for c in ASS.list_curves(p['idle']))
            loop_names=set(str(c.curve_name) for c in ASS.list_curves(LOOP))
            for curve in sorted(curve_names):
                assert ASS.add_curve(path,curve,False)
                keys=[]
                for f,(st,w) in enumerate(zip(p['times'],p['weights'])):
                    av=ASS.get_curve_value_at_time(LOOP,curve,st) if curve in loop_names else 0.0
                    bv=ASS.get_curve_value_at_time(p['idle'],curve,0) if curve in idle_names else av
                    value=av*(1-w)+bv*w
                    if curve=='movedata_speed':
                        value=ASS.get_curve_value_at_time(LOOP,curve,st)*speed_weight(f/FPS)
                    keys.append(unreal.CurveKeyframe(time=f/FPS,value=value,interp_mode='Linear'))
                assert ASS.set_curve_keys(path,curve,keys)
            unreal.EditorAssetLibrary.set_metadata_tag(unreal.EditorAssetLibrary.load_asset(path),'GeneratedFrom',LOOP+'; '+p['idle'])
            assert unreal.EditorAssetLibrary.save_asset(path,False)
            print('SAVED:',path)
            reread=ASS.get_anim_sequence_info(path)
            assert reread.frame_count==FRAMES and reread.bone_track_count==93 and reread.rate_scale==1
            end=pose(path,DURATION)
            idle_end=pose(p['idle'],0)
            error=max((end[b].translation-idle_end[b].translation).length() for b in end if b!='root')
            assert error<0.001, ('Idle endpoint mismatch',error)
            root_start=pose(path,0)['root'].translation
            root_end=end['root'].translation
            late=pose(path,BRAKE_END)['root'].translation
            assert (late-root_end).length()<0.05
            entry={'asset':path,'idle':p['idle'],'loop_start_time':p['start_time'],'loop_end_time':p['end_time'],
                   'duration':reread.duration,'frame_count':reread.frame_count,'bone_tracks':reread.bone_track_count,
                   'root_delta_cm':[root_end.x-root_start.x,root_end.y-root_start.y,root_end.z-root_start.z],
                   'max_local_rotation_step_deg':p['max_angle'],'idle_local_translation_error_cm':error,
                   'notify_count':reread.notify_count,'curves':len(curve_names)}
            report['outputs'].append(entry)
            print('VERIFIED:',json.dumps(entry))
        report_path=os.path.join(REPORT_DIR,'report.json')
        with open(report_path,'w',encoding='utf-8') as f:
            json.dump(report,f,indent=2)
        unreal.WorkflowService.attach_run_artifact(run,report_path,'file')
        unreal.WorkflowService.attach_run_artifact(run,os.path.abspath(__file__),'file')
        # Leave run active until visual review is complete.
        print('RUN_PENDING_VISUAL_REVIEW:',run)
    except Exception as error:
        unreal.WorkflowService.finish_run(run,'failed',str(error))
        raise


if __name__=='__main__':
    main()
