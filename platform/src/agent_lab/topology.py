"""M0 directed graph definitions."""

def directed_edges(kind: str, center: str = "agent_2") -> tuple[tuple[str, str], ...]:
    if kind == "chain":
        return (("agent_1", "agent_2"), ("agent_2", "agent_3"))
    if kind == "star_bidirectional":
        leaves = sorted({"agent_1", "agent_2", "agent_3"} - {center})
        return tuple((a, b) for leaf in leaves for a, b in ((center, leaf), (leaf, center)))
    raise ValueError(f"unknown topology: {kind}")


def incoming_for_round(messages, receiver_id: str, round_number: int):
    """Frozen mailbox: a round can read only messages from the preceding round."""
    return tuple(m for m in messages if m.receiver_id == receiver_id and m.round == round_number - 1)
