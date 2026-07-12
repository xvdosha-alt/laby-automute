package net.llm.screenshotbridge.api;

import java.util.List;

public final class AutoLoginStep {

    private final int slot;
    private final List<ContainerSlotDump> slots;

    public AutoLoginStep(int slot, List<ContainerSlotDump> slots) {
        this.slot = slot;
        this.slots = List.copyOf(slots);
    }

    public int slot() {
        return slot;
    }

    public List<ContainerSlotDump> slots() {
        return slots;
    }
}
