package net.llm.screenshotbridge.core;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

public final class ChatBuffer {

    private static final int MAX_ENTRIES = 2000;
    private static final int MAX_SEEN_IDS = 1000;

    private final List<Entry> entries = new ArrayList<>();
    private final ArrayDeque<UUID> recentIds = new ArrayDeque<>();
    private final Set<UUID> seenIds = new HashSet<>();
    private int seq;

    public synchronized int push(String timestamp, String nickname, String text) {
        return push(timestamp, nickname, text, false);
    }

    public synchronized int push(String timestamp, String nickname, String text, boolean alteredNick) {
        this.seq++;
        this.entries.add(new Entry(this.seq, timestamp, nickname, text, alteredNick));
        while (this.entries.size() > MAX_ENTRIES) {
            this.entries.remove(0);
        }
        return this.seq;
    }

    public synchronized boolean pushIfNew(
        UUID messageId,
        String timestamp,
        String nickname,
        String text
    ) {
        return pushIfNew(messageId, timestamp, nickname, text, false);
    }

    public synchronized boolean pushIfNew(
        UUID messageId,
        String timestamp,
        String nickname,
        String text,
        boolean alteredNick
    ) {
        if (messageId != null) {
            if (!this.seenIds.add(messageId)) {
                return false;
            }
            this.recentIds.addLast(messageId);
            while (this.recentIds.size() > MAX_SEEN_IDS) {
                UUID old = this.recentIds.removeFirst();
                this.seenIds.remove(old);
            }
        }
        this.push(timestamp, nickname, text, alteredNick);
        return true;
    }

    public synchronized List<Entry> pollSince(int since) {
        List<Entry> result = new ArrayList<>();
        for (Entry entry : this.entries) {
            if (entry.seq() > since) {
                result.add(entry);
            }
        }
        return result;
    }

    public synchronized int lastSeq() {
        return this.seq;
    }

    public record Entry(int seq, String time, String nick, String text, boolean alteredNick) {
    }
}
