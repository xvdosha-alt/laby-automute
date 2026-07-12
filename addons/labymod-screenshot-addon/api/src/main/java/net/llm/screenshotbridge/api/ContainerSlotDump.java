package net.llm.screenshotbridge.api;

public final class ContainerSlotDump {

    private final int slot;
    private final String itemId;
    private final int count;
    private final String name;
    private final boolean empty;

    public ContainerSlotDump(int slot, String itemId, int count, String name, boolean empty) {
        this.slot = slot;
        this.itemId = itemId;
        this.count = count;
        this.name = name;
        this.empty = empty;
    }

    public int slot() {
        return slot;
    }

    public String itemId() {
        return itemId;
    }

    public int count() {
        return count;
    }

    public String name() {
        return name;
    }

    public boolean empty() {
        return empty;
    }
}
