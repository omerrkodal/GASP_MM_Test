import unreal
import json
import math
import os

ASS = unreal.AnimSequenceService
CRAWL = '/Game/_GAME/Anims/Crawl/Transitions/Crawl_To_Crouch_Idle'
IDLE = '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop'
FOLDER = '/Game/_GAME/Anims/Crawl/Transitions'
NAME = 'Crawl_To_Stand_Idle'
OUTPUT = FOLDER + '/' + NAME
FPS, FRAMES, DURATION = 30, 46, 1.5
PUSH_END, BLEND_START, BLEND_END = 0.6, 0.3, 1.2
ARTIFACTS = os.path.join(unreal.Paths.project_saved_dir(), 'VibeUE', 'DirectCrawlToStand')


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u*u*u*(10+u*(-15+6*u))


def dot(a, b):
    return a.x*b.x+a.y*b.y+a.z*b.z


def cross(a, b):
    return unreal.Vector(a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x)


def qnorm(q):
    length = math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)
    return unreal.Quat(q.x/length,q.y/length,q.z/length,q.w/length)


def qmul(a,b):
    return qnorm(unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,
                            a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,
                            a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,
                            a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z))


def qinv(q):
    return unreal.Quat(-q.x,-q.y,-q.z,q.w)


def rotate(q,v):
    u=unreal.Vector(q.x,q.y,q.z)
    return v+cross(u,v)*(2*q.w)+cross(u,cross(u,v))*2


def between(a,b):
    a,b=a/a.length(),b/b.length()
    d=max(-1.0,min(1.0,dot(a,b)))
    if d>0.999999999:
        return unreal.Quat(0,0,0,1)
    if d<-.999999:
        axis=cross(a,unreal.Vector(1,0,0) if abs(a.x)<.9 else unreal.Vector(0,1,0))
        axis=axis/axis.length()
        return unreal.Quat(axis.x,axis.y,axis.z,0)
    axis=cross(a,b)
    return qnorm(unreal.Quat(axis.x,axis.y,axis.z,1+d))


def blend_quat(a,b,w):
    av,bv=[a.x,a.y,a.z,a.w],[b.x,b.y,b.z,b.w]
    d=sum(x*y for x,y in zip(av,bv))
    if d<0:
        d,bv=-d,[-v for v in bv]
    d=min(1.0,d)
    if d>.9995:
        values=[x*(1-w)+y*w for x,y in zip(av,bv)]
    else:
        theta=math.acos(d)
        sa,sb=math.sin((1-w)*theta)/math.sin(theta),math.sin(w*theta)/math.sin(theta)
        values=[x*sa+y*sb for x,y in zip(av,bv)]
    return qnorm(unreal.Quat(*values))


def pose(path,t,global_space=False):
    return {str(b.bone_name):b.transform for b in ASS.get_pose_at_time(path,t,global_space)}


def leg_globals(p):
    g={'root':p['root']}
    g['pelvis']=unreal.MathLibrary.compose_transforms(p['pelvis'],g['root'])
    for side in ['l','r']:
        parent='pelvis'
        for stem in ['thigh','calf','foot','ball']:
            bone=stem+'_'+side
            g[bone]=unreal.MathLibrary.compose_transforms(p[bone],g[parent])
            parent=bone
    return g


def solve_leg(p,side,target,foot_rotation):
    thigh,calf,foot='thigh_'+side,'calf_'+side,'foot_'+side
    g=leg_globals(p)
    a,b,c=g[thigh].translation,g[calf].translation,g[foot].translation
    l1,l2=(b-a).length(),(c-b).length()
    delta=target-a
    distance=delta.length()
    direction=delta/distance
    reach=min(l1+l2-.0001,max(abs(l1-l2)+.0001,distance))
    pole=(b-a)-direction*dot(b-a,direction)
    assert pole.length()>.00001, 'Degenerate animated knee plane'
    pole=pole/pole.length()
    x=(l1*l1-l2*l2+reach*reach)/(2*reach)
    height=math.sqrt(max(0,l1*l1-x*x))
    knee=a+direction*x+pole*height
    wanted=a+direction*reach
    thigh_q=qmul(between(b-a,knee-a),g[thigh].rotation)
    p[thigh].rotation=qmul(qinv(g['pelvis'].rotation),thigh_q)
    g=leg_globals(p)
    calf_q=qmul(between(g[foot].translation-g[calf].translation,wanted-g[calf].translation),g[calf].rotation)
    p[calf].rotation=qmul(qinv(g[thigh].rotation),calf_q)
    g=leg_globals(p)
    p[foot].rotation=qmul(qinv(g[calf].rotation),foot_rotation)
    error=(leg_globals(p)[foot].translation-target).length()
    assert error<.05, ('Foot target unreachable',side,error)
    return error


def build_samples():
    samples=[]
    max_foot_error=0.0
    for f in range(FRAMES):
        t=f/FPS
        a=pose(CRAWL,min(t,PUSH_END))
        b=pose(IDLE,(10+t-DURATION)%10)
        a['root'],b['root']=unreal.Transform(),unreal.Transform()
        ga,gb=leg_globals(a),leg_globals(b)
        w=smooth((t-BLEND_START)/(BLEND_END-BLEND_START))
        p={}
        for bone,at in a.items():
            bt=b[bone]
            tr=unreal.Transform()
            tr.translation=at.translation*(1-w)+bt.translation*w
            tr.rotation=blend_quat(at.rotation,bt.rotation,w)
            tr.scale3d=at.scale3d*(1-w)+bt.scale3d*w
            p[bone]=tr
        p['root']=unreal.Transform()
        for side in ['l','r']:
            foot,ball='foot_'+side,'ball_'+side
            target=ga[foot].translation*(1-w)+gb[foot].translation*w
            foot_q=blend_quat(ga[foot].rotation,gb[foot].rotation,w)
            scale=leg_globals(p)[foot].scale3d
            toe=p[ball].translation
            toe_offset=rotate(foot_q,unreal.Vector(toe.x*scale.x,toe.y*scale.y,toe.z*scale.z))
            toe_z=ga[ball].translation.z*(1-w)+gb[ball].translation.z*w
            target.z=max(target.z,toe_z-toe_offset.z)
            max_foot_error=max(max_foot_error,solve_leg(p,side,target,foot_q))
        # Retarget/post-process IK helpers must agree with the solved FK feet.
        final=leg_globals(p)
        ik_root=unreal.MathLibrary.compose_transforms(p['ik_foot_root'],p['root'])
        for side in ['l','r']:
            p['ik_foot_'+side]=unreal.MathLibrary.make_relative_transform(final['foot_'+side],ik_root)
        samples.append(p)
    return samples,max_foot_error


def phase_keys_from_pose(path):
    # Fixed identity root; mesh forward is +Y. +1 left knee leads, -1 right.
    leads=[]
    for f in range(FRAMES):
        p=pose(path,f/FPS,True)
        leads.append(p['calf_l'].translation.y-p['calf_r'].translation.y)
    # Dense bounded values follow knee position; anchor fully led start/end poses.
    peak_pos=max(leads)
    peak_neg=abs(min(leads))
    keys=[]
    for f,v in enumerate(leads):
        denom=peak_pos if v>=0 else peak_neg
        value=max(-1,min(1,v/max(denom,.0001)))
        if f==0:
            value=1 if v>=0 else -1
        if f==FRAMES-1:
            value=1 if v>=0 else -1
        keys.append((f/FPS,value))
    for f in range(FRAMES-1):
        if leads[f]*leads[f+1]<0:
            keys.append(((f+abs(leads[f])/(abs(leads[f])+abs(leads[f+1])))/FPS,0))
    return sorted(keys)


def curve_value(curve,t,names):
    w=smooth((t-BLEND_START)/(BLEND_END-BLEND_START))
    default=1.0 if curve in ['enable_warping','enable_orientationwarping'] else 0.0
    a=ASS.get_curve_value_at_time(CRAWL,curve,min(t,PUSH_END)) if curve in names[CRAWL] else default
    b=ASS.get_curve_value_at_time(IDLE,curve,(10+t-DURATION)%10) if curve in names[IDLE] else default
    return a*(1-w)+b*w


def validate_asset(path,samples):
    info=ASS.get_anim_sequence_info(path)
    assert info.frame_count==FRAMES and abs(info.duration-DURATION)<1e-6
    assert info.bone_track_count==93 and info.curve_count==6 and info.notify_count==0
    heights=[]
    helper_error=0.0
    foot_error=0.0
    root_drift=0.0
    for f in range(FRAMES):
        gp=pose(path,f/FPS,True)
        planned=leg_globals(samples[f])
        heights.append(gp['pelvis'].translation.z)
        root_drift=max(root_drift,gp['root'].translation.length())
        assert abs(gp['root'].rotation.w-1)<1e-6
        for side in ['l','r']:
            helper_error=max(helper_error,(gp['ik_foot_'+side].translation-gp['foot_'+side].translation).length())
            foot_error=max(foot_error,(gp['foot_'+side].translation-planned['foot_'+side].translation).length())
        lead=gp['calf_l'].translation.y-gp['calf_r'].translation.y
        assert abs(lead)<.001 or lead*ASS.get_curve_value_at_time(path,'phase',f/FPS)>0
    # 0.01cm allows native quaternion/float sampling differences, below 0.1mm.
    assert root_drift==0 and helper_error<.01 and foot_error<.01
    minimum_step=min(b-a for a,b in zip(heights,heights[1:]))
    assert minimum_step>-.05 and heights[-1]>90
    endpoint_errors=[]
    for output_time,source,source_time in [(0,CRAWL,0),(DURATION,IDLE,0)]:
        a,b=pose(path,output_time),pose(source,source_time)
        pos_err,rot_err=0.0,0.0
        for bone in a:
            if bone=='root':
                continue
            pos_err=max(pos_err,(a[bone].translation-b[bone].translation).length())
            x,y=a[bone].rotation,b[bone].rotation
            rot_err=max(rot_err,math.degrees(2*math.acos(min(1,abs(x.x*y.x+x.y*y.y+x.z*y.z+x.w*y.w)))))
        assert pos_err<.001 and rot_err<.1
        endpoint_errors.append({'position_cm':pos_err,'rotation_degrees':rot_err})
    return {'root_drift_cm':root_drift,'foot_helper_error_cm':helper_error,
            'native_vs_planned_foot_error_cm':foot_error,'minimum_pelvis_step_cm':minimum_step,
            'endpoint_errors':endpoint_errors,'pelvis_heights_cm':heights}


def main(update_existing=False):
    exists=unreal.EditorAssetLibrary.does_asset_exist(OUTPUT)
    assert update_existing or not exists, 'Asset already exists; update requires explicit opt-in.'
    infos={p:ASS.get_anim_sequence_info(p) for p in [CRAWL,IDLE]}
    skeleton=infos[CRAWL].skeleton_path
    assert infos[IDLE].skeleton_path==skeleton
    assert unreal.SkeletonService.create_skeleton_profile(skeleton).bone_count==93
    samples,foot_error=build_samples()
    heights=[p['pelvis'].translation.z for p in samples]
    assert min(b-a for a,b in zip(heights,heights[1:]))>-.05, 'A crouch/downward stage remains'
    run=json.loads(unreal.WorkflowService.start_run('Direct crawl to stand: remove crouch stage',json.dumps({'asset':OUTPUT,'sources':[CRAWL,IDLE],'duration':DURATION,'sourcePushCutoff':PUSH_END,'blend':[BLEND_START,BLEND_END],'rollback':os.path.join(ARTIFACTS,'before.json')})))['runId']
    try:
        if not exists:
            tracks=[unreal.BoneTrackData(bone_name=bone,keyframes=[unreal.AnimKeyframe(frame=f,time=f/FPS,position=p[bone].translation,rotation=p[bone].rotation,scale=p[bone].scale3d) for f,p in enumerate(samples)]) for bone in samples[0]]
            assert ASS.create_anim_sequence(skeleton,NAME,FOLDER,DURATION,FPS,tracks)
            print('CREATED:',OUTPUT)
        asset=unreal.EditorAssetLibrary.load_asset(OUTPUT)
        controller=asset.get_editor_property('controller')
        controller.open_bracket('Bake direct rising pose with foot paths')
        try:
            controller.set_number_of_frames(unreal.FrameNumber(FRAMES-1),True)
            for bone in samples[0]:
                assert controller.set_bone_track_keys(bone,[p[bone].translation for p in samples],[p[bone].rotation for p in samples],[p[bone].scale3d for p in samples],True)
        finally:
            controller.close_bracket()
        print('MODIFIED:',OUTPUT,'direct push-up to standing; crouch bridge removed')
        names={p:{str(c.curve_name) for c in ASS.list_curves(p)} for p in infos}
        curves=set().union(*names.values())
        existing={str(c.curve_name) for c in ASS.list_curves(OUTPUT)}
        for c in existing-curves:
            assert ASS.remove_curve(OUTPUT,c)
        for curve in sorted(curves):
            if curve not in existing:
                assert ASS.add_curve(OUTPUT,curve,False)
            values=phase_keys_from_pose(OUTPUT) if curve=='phase' else [(i/60,curve_value(curve,i/60,names)) for i in range(round(DURATION*60)+1)]
            keys=[unreal.RichCurveKey(time=t,value=v,interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR,tangent_mode=unreal.RichCurveTangentMode.RCTM_AUTO) for t,v in values]
            identifier=unreal.AnimationCurveIdentifier()
            identifier.set_curve_identifier(curve,unreal.RawCurveTrackTypes.RCT_FLOAT)
            assert controller.set_curve_keys(identifier,keys,True)
        # Earlier draft copied events from the discarded crouch-to-stand bridge.
        for i in reversed(range(ASS.get_anim_sequence_info(OUTPUT).notify_count)):
            assert ASS.remove_notify(OUTPUT,i)
        asset.set_editor_property('force_root_lock',True)
        asset.set_editor_property('loop',False)
        assert ASS.set_enable_root_motion(OUTPUT,True)
        assert ASS.set_root_motion_root_lock(OUTPUT,'RefPose')
        assert ASS.set_rate_scale(OUTPUT,1)
        unreal.EditorAssetLibrary.set_metadata_tag(asset,'GeneratedFrom','; '.join([CRAWL,IDLE]))
        assert unreal.EditorAssetLibrary.save_asset(OUTPUT,False)
        print('SAVED:',OUTPUT)
        verification=validate_asset(OUTPUT,samples)
        os.makedirs(ARTIFACTS,exist_ok=True)
        report={'run':run,'asset':OUTPUT,'sources':[CRAWL,IDLE],'duration':DURATION,'frames':FRAMES,
                'push_source_end':PUSH_END,'standing_blend':[BLEND_START,BLEND_END],
                'pelvis_heights_cm':heights,'minimum_pelvis_step_cm':min(b-a for a,b in zip(heights,heights[1:])),
                'max_foot_target_error_cm':foot_error,'phase_keys':phase_keys_from_pose(OUTPUT),
                'gameplay_wiring':'unchanged','notifies':0,'native_verification':verification}
        with open(os.path.join(ARTIFACTS,'report.json'),'w',encoding='utf-8') as f:
            json.dump(report,f,indent=2)
        for file in ['before.json','report.json']:
            unreal.WorkflowService.attach_run_artifact(run,os.path.join(ARTIFACTS,file),'file')
        unreal.WorkflowService.attach_run_artifact(run,os.path.abspath(__file__),'file')
        print('RUN_PENDING_VISUAL_REVIEW:',run)
    except Exception as e:
        unreal.WorkflowService.finish_run(run,'failed',str(e))
        raise


if __name__=='__main__':
    main()
