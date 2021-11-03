import numpy as np
from .env_base import BaseEnv
from ..core.catalog import Catalog
from ..tasks import HeadingTask, HeadingAndAltitudeTask, HeadingContinuousTask


class SingleControlEnv(BaseEnv):
    """
    SingleControlEnv is an fly-control env for single agent with no enemy fighters.
    """
    def __init__(self, config_name: str):
        super().__init__(config_name)
        assert self.num_aircrafts == 1, "only support one fighter"

    def load_task(self):
        taskname = getattr(self.config, 'task', 'heading_task')
        if taskname == 'heading_task':
            self.task = HeadingTask(self.config)
        elif taskname == 'heading_altitude_task':
            self.task = HeadingAndAltitudeTask(self.config)
        elif taskname == 'heading_continuous_task':
            self.task = HeadingContinuousTask(self.config)
        else:
            raise NotImplementedError(f'Unknown taskname: {taskname}')
        self.observation_space = self.task.observation_space
        self.action_space = self.task.action_space

    def reset(self):
        self.current_step = 0
        self.reset_conditions()
        next_observation = self.get_observation()
        self.task.reset(self)
        return next_observation

    def reset_conditions(self):
        new_init_state = self.aircraft_configs[0].get('init_state', {})  # type: dict
        new_init_state.update({
            'ic_psi_true_deg': np.random.uniform(0, 360),
            'ic_u_fps': np.random.uniform(500, 1000),
            'ic_v_fps': np.random.uniform(-100, 100),
            'ic_w_fps': np.random.uniform(-100, 100),
            'ic_p_rad_sec': np.random.uniform(-np.pi, np.pi),
            'ic_q_rad_sec': np.random.uniform(-np.pi, np.pi),
            'ic_r_rad_sec': np.random.uniform(-np.pi, np.pi),
        })
        self.sims[0].reload(new_init_state)

    def step(self, action: list):
        """Run one timestep of the environment's dynamics. When end of
        episode is reached, you are responsible for calling `reset()`
        to reset this environment's state. Accepts an action and 
        returns a tuple (observation, reward_visualize, done, info).

        Args:
            action (dict{str: np.array}): the agents' action, with same length as action variables.

        Returns:
            (tuple):
                state: agent's observation of the current environment
                reward_visualize: amount of reward_visualize returned after previous action
                done: whether the episode has ended, in which case further step() calls are undefined
                info: auxiliary information
        """
        self.current_step += 1
        info = {}
        action = self.task.normalize_action(self, action)
        # run JSBSim for one step
        next_observation = self.make_step(action)

        reward = np.zeros(self.num_aircrafts)
        for agent_id in range(self.num_aircrafts):
            reward[agent_id], info = self.task.get_reward(self, agent_id, info)

        done = False
        for agent_id in range(self.num_aircrafts):
            agent_done, info = self.task.get_termination(self, agent_id, info)
            done = agent_done or done

        return next_observation, reward, done, info

    def get_observation(self):
        """
        get state observation from sim.

        Returns:
            (OrderedDict): the same format as self.observation_space
        """
        # generate observation (gym.Env output)
        next_observation = []
        for agent_id in range(self.num_aircrafts):
            next_observation.append(self.sims[agent_id].get_property_values(self.task.state_var))
        next_observation = self.task.normalize_observation(self, next_observation)
        return next_observation

    def close(self):
        """Cleans up this environment's objects.

        Environments automatically close() when garbage collected or when the program exits.
        """
        for agent_id in range(self.num_aircrafts):
            if self.sims[agent_id]:
                self.sims[agent_id].close()

    def render(self, mode="human", **kwargs):
        """Renders the environment.

        The set of supported modes varies per environment. (And some

        environments do not support rendering at all.) By convention,

        if mode is:

        - human: print on the terminal
        - csv: output to cvs files

        Note:

            Make sure that your class's metadata 'render.modes' key includes
              the list of supported modes. It's recommended to call super()
              in implementations to use the functionality of this method.
        :param mode: str, the mode to render with
        """
        render_list = []
        for agent_id in range(self.num_aircrafts):
            render_list.append(np.array(self.sims[agent_id].get_property_values(self.task.render_var)))
        return np.hstack(render_list)
