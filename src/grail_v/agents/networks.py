"""An actor and two critics.

Two critics rather than one because a CMDP has two returns to estimate and
they behave nothing alike. The reward return is bounded, low variance, and
almost constant -- it is the negative activation cost, so it takes three
values. The cost return is a sum of probabilities around 1e-4 with a heavy
right tail. Sharing a trunk between them would let the easy head's gradients
dominate the representation the hard one depends on, and the hard one is the
head the constraint is read from.

The architecture is the frozen profile's: two hidden layers of 64 with tanh.
Small on purpose. The observation is thirty-five columns of engineered
features, not pixels, and a larger network would spend its capacity fitting
the trace rather than the structure.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn

#: Orthogonal gain for hidden layers under tanh.
_HIDDEN_GAIN = 2.0**0.5

#: The policy head starts near-uniform so early rollouts explore all three
#: actions. At a 1e-4 budget a policy that collapsed onto RF in the first few
#: updates would see no duplication outcomes at all and never recover the
#: gradient that would tell it to duplicate.
_POLICY_GAIN = 0.01


def _mlp(inputs: int, hidden: Sequence[int], outputs: int, output_gain: float) -> nn.Sequential:
    layers: list[nn.Module] = []
    width = inputs
    for size in hidden:
        linear = nn.Linear(width, size)
        nn.init.orthogonal_(linear.weight, _HIDDEN_GAIN)
        nn.init.zeros_(linear.bias)
        layers += [linear, nn.Tanh()]
        width = size
    head = nn.Linear(width, outputs)
    nn.init.orthogonal_(head.weight, output_gain)
    nn.init.zeros_(head.bias)
    layers.append(head)
    return nn.Sequential(*layers)


class ActorCritic(nn.Module):
    """Categorical policy over the three actions, with separate value heads."""

    def __init__(
        self,
        observation_width: int,
        actions: int,
        *,
        actor_hidden: Sequence[int],
        reward_critic_hidden: Sequence[int],
        cost_critic_hidden: Sequence[int],
    ) -> None:
        super().__init__()
        self.actor = _mlp(observation_width, actor_hidden, actions, _POLICY_GAIN)
        self.reward_critic = _mlp(observation_width, reward_critic_hidden, 1, 1.0)
        self.cost_critic = _mlp(observation_width, cost_critic_hidden, 1, 1.0)

    def distribution(self, observation: torch.Tensor) -> torch.distributions.Categorical:
        return torch.distributions.Categorical(logits=self.actor(observation))

    def values(self, observation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return (
            self.reward_critic(observation).squeeze(-1),
            self.cost_critic(observation).squeeze(-1),
        )

    @torch.no_grad()
    def act(self, observation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample an action and report everything the update will need."""

        distribution = self.distribution(observation)
        action = distribution.sample()
        reward_value, cost_value = self.values(observation)
        return action, distribution.log_prob(action), reward_value, cost_value

    def evaluate(
        self, observation: torch.Tensor, action: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        distribution = self.distribution(observation)
        reward_value, cost_value = self.values(observation)
        return (
            distribution.log_prob(action),
            distribution.entropy(),
            reward_value,
            cost_value,
        )


__all__ = ["ActorCritic"]
