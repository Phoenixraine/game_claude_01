from . import z_legs, z_torso, z_arms, z_head, z_extra


def build_all(P):
    for s in (1, -1):
        z_legs.build_leg(P, s)
    z_torso.build_torso(P)
    z_torso.build_pelvis(P)
    z_torso.build_reactor(P)
    z_arms.build_all_arms(P)
    z_head.build_head(P)
    z_extra.build_extra(P)
