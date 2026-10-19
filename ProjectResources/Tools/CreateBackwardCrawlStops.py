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
REPORT_DIR = os.path.join(unreal.Paths.project_saved_dir(), 'VibeUE', 'BackwardCrawlStops')


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u*u*u*(10 + u*(-15 + 6*u))


def progress(t):
    if t <= BRAKE_START:
        return t
    u = min(1.0, (t - BRAKE_START) / (BRAKE_END - BRAKE_START))
    return BRAKE_START + (BRAKE_END - BRAKE_START)*(u - u**3 + 0.5*u**4)


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


def quat_mul(a, b):
    return unreal.Quat(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,
                       a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,
                       a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w,
                       a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z)


def body_heading(p):
    v = p['spine_05'].translation - p['pelvis'].translation
    return math.atan2(v.x, v.y)


def stabilize_body(path):
    """Keep horizontal pelvis position and body heading on a smooth endpoint path.

    Root motion and every local child-bone track stay untouched. Corrections are
    around mesh up, converted into the pelvis parent's (root) space.
    """
    local = [pose(path,f/FPS) for f in range(FRAMES)]
    global_ = [pose(path,f/FPS,True) for f in range(FRAMES)]
    a,b = local[0]['pelvis'].translation,local[-1]['pelvis'].translation
    ha,hb = body_heading(global_[0]),body_heading(global_[-1])
    dh = (hb-ha+math.pi) % (2*math.pi)-math.pi
    positions,rotations,scales=[],[],[]
    for f,p in enumerate(local):
        w=smooth((f/FPS-BLEND_START)/(BLEND_END-BLEND_START))
        tr=p['pelvis']
        positions.append(unreal.Vector(a.x+(b.x-a.x)*w,a.y+(b.y-a.y)*w,tr.translation.z))
        heading=ha+dh*w
        angle=(body_heading(global_[f])-heading+math.pi) % (2*math.pi)-math.pi
        correction=unreal.Quat(0,0,math.sin(angle/2),math.cos(angle/2))
        root=p['root'].rotation
        inverse=unreal.Quat(-root.x,-root.y,-root.z,root.w)
        parent_delta=quat_mul(quat_mul(inverse,correction),root)
        rotations.append(quat_mul(parent_delta,tr.rotation))
        scales.append(tr.scale3d)
    asset=unreal.EditorAssetLibrary.load_asset(path)
    controller=asset.get_editor_property('controller')
    controller.open_bracket('Stabilize backward crawl pelvis and body heading')
    try:
        assert controller.set_bone_track_keys('pelvis',positions,rotations,scales,True)
    finally:
        controller.close_bracket()
    print('MODIFIED:',path,'pelvis XY and mesh-up heading only')


def fit_phase_from_knees(path, side):
    info=ASS.get_anim_sequence_info(path)
    leads=[]
    for f in range(info.frame_count):
        p=pose(path,f/info.frame_rate,True)
        axis=p['spine_05'].translation-p['pelvis'].translation
        d=p['calf_l'].translation-p['calf_r'].translation
        length=math.sqrt(axis.x*axis.x+axis.y*axis.y)
        leads.append((d.x*axis.x+d.y*axis.y)/length)
    sign=1 if side=='Left' else -1
    opposite=min(range(len(leads)),key=lambda f:sign*leads[f])
    crossings=[(f+abs(leads[f])/(abs(leads[f])+abs(leads[f+1])))/info.frame_rate
               for f in range(len(leads)-1) if leads[f]*leads[f+1]<0]
    assert len(crossings)==2 and sign*leads[0]>0 and sign*leads[-1]>0
    recovery=next(f for f in range(opposite+1,len(leads))
                  if sign*leads[f]>=0.9*sign*leads[-1])
    points=[(0,sign),(crossings[0],0),(opposite/info.frame_rate,-sign),
            (crossings[1],0),(recovery/info.frame_rate,sign),(info.duration,sign)]
    assert all(a[0]<b[0] for a,b in zip(points,points[1:]))
    keys=[unreal.RichCurveKey(time=t,value=v,interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR,
                             tangent_mode=unreal.RichCurveTangentMode.RCTM_AUTO) for t,v in points]
    controller=unreal.EditorAssetLibrary.load_asset(path).get_editor_property('controller')
    identifier=unreal.AnimationCurveIdentifier()
    identifier.set_curve_identifier('phase',unreal.RawCurveTrackTypes.RCT_FLOAT)
    assert controller.set_curve_keys(identifier,keys,True)
    print('MODIFIED:',path,'phase follows knees (+1 left, -1 right)',points)
    return points


def match_forward_curves(path, forward):
    wanted={str(c.curve_name) for c in ASS.list_curves(forward)}
    existing={str(c.curve_name) for c in ASS.list_curves(path)}
    for curve in sorted(existing-wanted):
        assert ASS.remove_curve(path,curve)
        print('REMOVED:',path,'curve',curve)
    asset=unreal.EditorAssetLibrary.load_asset(path)
    controller=asset.get_editor_property('controller')
    modes={'Linear':unreal.RichCurveInterpMode.RCIM_LINEAR,
           'Constant':unreal.RichCurveInterpMode.RCIM_CONSTANT,
           'Cubic':unreal.RichCurveInterpMode.RCIM_CUBIC}
    tangents={'Auto':unreal.RichCurveTangentMode.RCTM_AUTO,
              'User':unreal.RichCurveTangentMode.RCTM_USER,
              'Break':unreal.RichCurveTangentMode.RCTM_BREAK}
    controller.open_bracket('Match forward crawl stop curve values and interpolation')
    try:
        for curve in sorted(wanted):
            if curve not in existing:
                assert ASS.add_curve(path,curve,False)
            native_keys=[]
            for key in ASS.get_curve_keyframes(forward,curve):
                # UE's Python RichCurveKey does not expose tangent values.
                # These clips use linear changing keys and a flat cubic key.
                assert key.interp_mode!='Cubic' or (key.arrive_tangent==0 and key.leave_tangent==0)
                native_keys.append(unreal.RichCurveKey(time=key.time,value=key.value,
                                   interp_mode=modes[key.interp_mode],tangent_mode=tangents[key.tangent_mode]))
            identifier=unreal.AnimationCurveIdentifier()
            identifier.set_curve_identifier(curve,unreal.RawCurveTrackTypes.RCT_FLOAT)
            assert controller.set_curve_keys(identifier,native_keys,True)
    finally:
        controller.close_bracket()
    fit_phase_from_knees(path,forward.rsplit('_',1)[1])
    print('MODIFIED:',path,'forward-stop curves with pose-derived phase')
    return wanted


def plan(side, loop_info, loop_poses):
    idle = BASE + '/Idle/Crawl_Idle_Loop_' + side
    forward = OUT + '/Crawl_Stop_F_' + side
    lead=lambda p:p['calf_l'].translation.y-p['calf_r'].translation.y
    forward_leads=[lead(pose(forward,f/FPS,True)) for f in range(FRAMES)]
    source_leads=[lead(p) for p in loop_poses]
    sign=1 if side=='Left' else -1
    middle_frame=min(range(1,FRAMES-1),key=lambda f:sign*forward_leads[f])
    return_frame=next(f for f in range(middle_frame+1,FRAMES)
                      if sign*forward_leads[f]>=0.9*sign*forward_leads[-1])
    extrema=[f for f in range(1,len(source_leads)-1)
             if (source_leads[f]-source_leads[f-1])*(source_leads[f+1]-source_leads[f])<0]
    candidates=[]
    for i in range(2,len(extrema)):
        a,b,c=extrema[i],extrema[i-1],extrema[i-2]
        if sign*source_leads[a]>8 and sign*source_leads[b]<-8 and sign*source_leads[c]>8:
            candidates.append((a,b,c))
    assert candidates, 'No complete matching backward knee cycle'
    target=[forward_leads[0],forward_leads[middle_frame],forward_leads[-1]]
    phase_frames=min(candidates,key=lambda fs:sum((source_leads[f]-v)**2 for f,v in zip(fs,target)))
    start_frame,middle_source,end_frame=phase_frames
    start_time,end_time=start_frame/FPS,end_frame/FPS
    mid_t,end_t=middle_frame/FPS,return_frame/FPS
    v0=(middle_source-start_frame)/mid_t
    vm=(end_frame-start_frame)/end_t

    def source_frame(t):
        if t>=end_t:
            return end_frame
        if t<=mid_t:
            ta,tb,a,b,va,vb=0,mid_t,start_frame,middle_source,v0,vm
        else:
            ta,tb,a,b,va,vb=mid_t,end_t,middle_source,end_frame,vm,0
        u=(t-ta)/(tb-ta)
        return (2*u**3-3*u**2+1)*a+(u**3-2*u**2+u)*(tb-ta)*va+(-2*u**3+3*u**2)*b+(u**3-u**2)*(tb-ta)*vb

    origin = pose(LOOP, start_time)['root'].translation
    idle_duration = ASS.get_animation_length(idle)
    samples, times, weights = [], [], []
    for f in range(FRAMES):
        t = f/FPS
        source_time = source_frame(t)/FPS
        a = pose(LOOP, source_time)
        # End at idle frame zero with its natural incoming breathing velocity.
        b = pose(idle, (idle_duration+t-DURATION) % idle_duration)
        # Keep the complete alternating step; settle only after the opposite knee leads.
        w = smooth((t-1.2)/(1.75-1.2))
        result = {}
        for bone, at in a.items():
            bt = b[bone]
            result[bone] = transform(at.translation*(1-w)+bt.translation*w,
                                     quat_blend(at.rotation,bt.rotation,w),
                                     at.scale3d*(1-w)+bt.scale3d*w)
        # Root braking remains independent of the finishing leg recovery.
        root = pose(LOOP,start_time-progress(t))['root']
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
    source_local=[pose(LOOP,f/FPS) for f in range(end_frame,start_frame+1)]
    source_max=0.0
    for a,b in zip(source_local,source_local[1:]):
        for bone in a:
            qa,qb=a[bone].rotation,b[bone].rotation
            dot=abs(qa.x*qb.x+qa.y*qb.y+qa.z*qb.z+qa.w*qb.w)
            source_max=max(source_max,math.degrees(2*math.acos(min(1.0,dot))))
    assert max_angle <= source_max*1.25+1, ('retiming exceeds source joint speed',side,max_angle,source_max)
    assert samples[-1]['root'].translation.y < -1, 'Expected backward root travel'
    tracks=[]
    for bone in samples[0]:
        keys=[unreal.AnimKeyframe(frame=f,time=f/FPS,position=p[bone].translation,
                                 rotation=p[bone].rotation,scale=p[bone].scale3d)
              for f,p in enumerate(samples)]
        tracks.append(unreal.BoneTrackData(bone_name=bone,keyframes=keys))
    return dict(side=side,idle=idle,start_time=start_time,end_time=end_time,
                samples=samples,times=times,weights=weights,tracks=tracks,max_angle=max_angle,
                phase_frames=phase_frames,middle_output_frame=middle_frame,return_output_frame=return_frame)


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
    report={'run':run,'outputs':[],'method':'Complete reversed loop knee cycle, root deceleration, late idle blending, smooth pelvis/heading, five matching forward-stop curves, and knee-derived phase (+1 left / -1 right); no gameplay wiring.'}
    try:
        for p in plans:
            name='Crawl_Stop_B_'+p['side']
            path=ASS.create_anim_sequence(info.skeleton_path,name,OUT,DURATION,FPS,p['tracks'])
            assert path, name+' creation failed'
            print('CREATED:',path)
            assert ASS.set_enable_root_motion(path,True)
            assert ASS.set_root_motion_root_lock(path,'RefPose')
            assert ASS.set_rate_scale(path,1)
            stabilize_body(path)
            curve_names=match_forward_curves(path,OUT+'/Crawl_Stop_F_'+p['side'])
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
            sign=1 if p['side']=='Left' else -1
            lead_order=[]
            for f in range(FRAMES):
                gp=pose(path,f/FPS,True)
                lead=gp['calf_l'].translation.y-gp['calf_r'].translation.y
                state=1 if lead>3 else -1 if lead<-3 else 0
                if state and (not lead_order or lead_order[-1]!=state):
                    lead_order.append(state)
            assert lead_order==[sign,-sign,sign], ('Incomplete knee cycle',lead_order)
            entry={'asset':path,'idle':p['idle'],'loop_start_time':p['start_time'],'loop_end_time':p['end_time'],
                   'source_knee_phase_frames':p['phase_frames'],'knee_lead_order':lead_order,
                   'opposite_knee_output_frame':p['middle_output_frame'],'return_output_frame':p['return_output_frame'],
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
