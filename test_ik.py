import math
import numpy as np

def compute_ik(tx, ty, tz, base_pos=(0, 0, 0.1), l1=0.05, l2=0.45, l3=0.45):
    """
    Computes analytical IK for the new 3-link arm.
    base_pos: Position of the robot_base.
    l1: Z-offset from base to shoulder joint.
    l2: Length of upper arm (link2).
    l3: Length of forearm (link3).
    """
    # 1. Target relative to base
    rx = tx - base_pos[0]
    ry = ty - base_pos[1]
    rz = tz - base_pos[2]

    # 2. Yaw (Base rotation)
    yaw = math.atan2(ry, rx)

    # 3. Distance from shoulder joint to target
    # The shoulder joint is at z = base_pos[2] + l1 relative to world,
    # or z = l1 relative to robot_base.
    shoulder_z = l1

    # Radial distance in the XY plane
    r = math.hypot(rx, ry)

    # Vertical distance from shoulder joint
    dz = rz - shoulder_z

    # Direct distance from shoulder to target
    d = math.hypot(r, dz)

    # Check reachability
    if d > (l2 + l3):
        # Target is too far, scale down d to max reach
        # Alternatively, we just stretch out fully
        d = l2 + l3 - 1e-4

    # Law of cosines for elbow angle
    # d^2 = l2^2 + l3^2 - 2*l2*l3*cos(pi - elbow)
    # cos_elbow_inner = (l2^2 + l3^2 - d^2) / (2 * l2 * l3)
    cos_theta3 = (d**2 - l2**2 - l3**2) / (2 * l2 * l3)
    # Clamp to [-1, 1] to avoid math domain errors
    cos_theta3 = max(-1.0, min(1.0, cos_theta3))

    # Elbow angle
    # The MuJoCo model has elbow hinge along Y axis.
    # Positive rotation bends it "down" or "up" depending on local axes.
    # We will assume elbow bends down (negative pitch) or up (positive pitch).
    elbow = math.acos(cos_theta3)

    # Law of cosines for shoulder angle
    # Angle from shoulder to target
    alpha = math.atan2(dz, r)
    # Angle between direct line and upper arm
    cos_beta = (l2**2 + d**2 - l3**2) / (2 * l2 * d)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.acos(cos_beta)

    # Shoulder angle
    # Note: Mujoco Y-axis hinge. In our generator:
    # link2 has joint_shoulder (axis=0 1 0).
    # Z is up, X is forward.
    # At 0 degrees, it points straight up along Z axis.
    # Wait, the generator says:
    # <geom type="capsule" fromto="0 0 0 0 0 0.45"... />
    # So 0 degrees = straight up!
    # Let's adjust for this.
    # The angle `alpha + beta` is the angle from the XY plane up to the arm.
    # If it points straight up, that's pi/2 from XY plane.
    # So if zero position is straight up, we need to subtract from pi/2.

    shoulder_angle_from_horizontal = alpha + beta
    # MuJoCo zero is straight up.
    # If Y is the hinge, rotating around Y:
    # X_new = X*cos(theta) + Z*sin(theta)
    # Z_new = -X*sin(theta) + Z*cos(theta)
    # Positive rotation tips it forward (+X).
    shoulder = math.pi/2 - shoulder_angle_from_horizontal

    return yaw, shoulder, -elbow # -elbow or +elbow depends on convention, let's test

print(compute_ik(0.6, 0.0, 0.3))
