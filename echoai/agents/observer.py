from echoai.agents.agent import Agent


class Observer(Agent):

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)