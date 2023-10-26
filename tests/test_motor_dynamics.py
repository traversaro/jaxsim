from typing import Union

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from pytest import param as p

from jaxsim.high_level.common import VelRepr
from jaxsim.high_level.model import Model

from . import utils_models, utils_rng
from .utils_models import Robot


@pytest.mark.parametrize(
    "robot, vel_repr",
    [
        p(*[Robot.DoublePendulum, VelRepr.Inertial], id="DoublePendulum-Inertial"),
        p(*[Robot.DoublePendulum, VelRepr.Body], id="DoublePendulum-Body"),
        p(*[Robot.DoublePendulum, VelRepr.Mixed], id="DoublePendulum-Mixed"),
        p(*[Robot.Ur10, VelRepr.Inertial], id="Ur10-Inertial"),
        p(*[Robot.Ur10, VelRepr.Body], id="Ur10-Body"),
        p(*[Robot.Ur10, VelRepr.Mixed], id="Ur10-Mixed"),
        p(*[Robot.AnymalC, VelRepr.Inertial], id="AnymalC-Inertial"),
        p(*[Robot.AnymalC, VelRepr.Body], id="AnymalC-Body"),
        p(*[Robot.AnymalC, VelRepr.Mixed], id="AnymalC-Mixed"),
        p(*[Robot.Cassie, VelRepr.Inertial], id="Cassie-Inertial"),
        p(*[Robot.Cassie, VelRepr.Body], id="Cassie-Body"),
        p(*[Robot.Cassie, VelRepr.Mixed], id="Cassie-Mixed"),
    ],
)
def test_motor_dynamics(robot: utils_models.Robot, vel_repr: VelRepr) -> None:
    """
    Unit test of the ABA algorithm against FD computed from the EoM considering motor dynamics.
    """

    urdf_file_path = utils_models.ModelFactory.get_model_description(robot=robot)

    # Insert model into the simulator
    model = Model.build_from_model_description(
        model_description=urdf_file_path,
        vel_repr=vel_repr,
        is_urdf=True,
    ).mutable(mutable=True, validate=True)

    # Initialize the model with a random state
    model.data.model_state = utils_rng.random_physics_model_state(
        physics_model=model.physics_model
    )

    # Initialize the model with a random input
    model.data.model_input = utils_rng.random_physics_model_input(
        physics_model=model.physics_model
    )

    # Get the joint torques
    tau = jax.random.uniform(
        key=jax.random.PRNGKey(42), shape=(model.dofs(),), minval=-100.0, maxval=100.0
    ).block_until_ready()

    with jax.disable_jit(True):
        print("=====================================================")
        print("============ Test without motor dynamics ============")
        print("=====================================================")

        C_v̇_WB, crb = model.forward_dynamics_crb(tau=tau)

        print("C_v̇_WB: ", C_v̇_WB)
        print("CRB: ", crb)

        a_WB, aba = model.forward_dynamics_aba(tau=tau)
        print("a_WB: ", a_WB)
        print("ABA: ", aba)

        assert a_WB == pytest.approx(C_v̇_WB, rel=0.1)
        assert aba == pytest.approx(crb, rel=0.1)

        print("=====================================================")
        print("============ Test with motor dynamics ===============")
        print("=====================================================")

        IM = jnp.array([5e-4] * model.dofs())
        GR = jnp.array([100.0] * model.dofs())
        KV = jnp.array([0.0003] * model.dofs())

        # Set motor parameters
        model.set_motor_inertias(IM)
        model.set_motor_gear_ratios(GR)
        model.set_motor_viscous_frictions(KV)

        C_v̇_WB, crb = model.forward_dynamics_crb(tau=tau)
        print("C_v̇_WB: ", C_v̇_WB)
        print("CRB: ", crb)

        a_WB, aba = model.forward_dynamics_aba(tau=tau)
        print("a_WB: ", a_WB)
        print("ABA: ", aba)

        assert C_v̇_WB == pytest.approx(a_WB, rel=0.1)
        assert crb == pytest.approx(aba, rel=0.1)

        print("=====================================================")
        print("================ Inertia set to zero ================")
        print("=====================================================")

        model.set_motor_inertias(jnp.array([0.0] * model.dofs()))

        C_v̇_WB, crb = model.forward_dynamics_crb(tau=tau)
        print("C_v̇_WB: ", C_v̇_WB)
        print("CRB: ", crb)

        a_WB, aba = model.forward_dynamics_aba(tau=tau)
        print("a_WB: ", a_WB)
        print("ABA: ", aba)

        np.testing.assert_allclose(a_WB, C_v̇_WB, atol=1e-3)
        np.testing.assert_allclose(aba, crb, atol=1e-3)

        assert C_v̇_WB == pytest.approx(a_WB, abs=1e-3)
        assert crb == pytest.approx(aba, abs=1e-3)
