package net.llm.screenshotbridge.v1_20_1;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import net.labymod.api.models.Implements;
import net.llm.screenshotbridge.api.AutoLoginResult;
import net.llm.screenshotbridge.api.AutoLoginStep;
import net.llm.screenshotbridge.api.BridgePlayer;
import net.llm.screenshotbridge.api.ContainerSlotDump;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.multiplayer.PlayerInfo;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.ClickType;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;

@Implements(BridgePlayer.class)
public class VersionedBridgePlayer implements BridgePlayer {

    private static final long ACTION_TIMEOUT_SECONDS = 5;
    private static final long AUTOLOGIN_TIMEOUT_SECONDS = 120;
    private static final long CONTAINER_OPEN_TIMEOUT_MS = 15_000;
    private static final long CONTAINER_CHANGE_TIMEOUT_MS = 15_000;
    private static final long POLL_INTERVAL_MS = 50;
    private static final long CLICK_DELAY_MS = 400;
    private static final long LITE_COMMAND_DELAY_MS = 500;
    private static final long CONTAINER_SETTLE_MS = 400;
    private static final int OUTSIDE_SLOT = -999;
    private static final long ALTERED_NICK_CACHE_MS = 5_000;

    private volatile long alteredNickCacheAt;
    private volatile Set<String> alteredNickCache = Set.of();

    @Override
    public String getLocalNickname() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null || minecraft.player == null) {
            return null;
        }
        return minecraft.player.getGameProfile().getName();
    }

    @Override
    public boolean isInWorld() {
        Minecraft minecraft = Minecraft.getInstance();
        return minecraft != null && minecraft.player != null && minecraft.level != null;
    }

    @Override
    public void sendChat(String message) throws Exception {
        runOnClientThread(() -> {
            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft.player == null || minecraft.player.connection == null) {
                throw new IllegalStateException("not_in_world");
            }
            if (message.startsWith("/")) {
                minecraft.player.connection.sendCommand(message.substring(1));
            } else {
                minecraft.player.connection.sendChat(message);
            }
        });
    }

    @Override
    public List<String> getOnlinePlayerNicks() throws Exception {
        return runOnClientThread(() -> {
            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft.player == null || minecraft.player.connection == null) {
                return List.of();
            }
            Collection<PlayerInfo> online = minecraft.player.connection.getOnlinePlayers();
            TreeSet<String> nicks = new TreeSet<>(String.CASE_INSENSITIVE_ORDER);
            for (PlayerInfo info : online) {
                if (info == null || info.getProfile() == null) {
                    continue;
                }
                String name = info.getProfile().getName();
                if (name != null && !name.isBlank()) {
                    nicks.add(name);
                }
            }
            return new ArrayList<>(nicks);
        });
    }

    @Override
    public boolean hasAlteredNickDisplay(String nick) {
        if (nick == null || nick.isBlank()) {
            return false;
        }
        try {
            return getAlteredNickCache().contains(nick.trim().toLowerCase(Locale.ROOT));
        } catch (Exception e) {
            return false;
        }
    }

    private Set<String> getAlteredNickCache() throws Exception {
        long now = System.currentTimeMillis();
        if (now - this.alteredNickCacheAt < ALTERED_NICK_CACHE_MS) {
            return this.alteredNickCache;
        }

        return runOnClientThread(() -> {
            long refreshedAt = System.currentTimeMillis();
            if (refreshedAt - this.alteredNickCacheAt < ALTERED_NICK_CACHE_MS) {
                return this.alteredNickCache;
            }

            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft == null || minecraft.player == null || minecraft.player.connection == null) {
                this.alteredNickCache = Set.of();
                this.alteredNickCacheAt = refreshedAt;
                return this.alteredNickCache;
            }

            Set<String> altered = new HashSet<>();
            for (PlayerInfo info : minecraft.player.connection.getOnlinePlayers()) {
                if (info == null || info.getProfile() == null) {
                    continue;
                }
                String profileName = info.getProfile().getName();
                if (profileName == null || profileName.isBlank()) {
                    continue;
                }
                if (info.getTabListDisplayName() == null) {
                    continue;
                }
                String display = info.getTabListDisplayName().getString().trim();
                if (display.startsWith("~")) {
                    altered.add(profileName.toLowerCase(Locale.ROOT));
                    continue;
                }
                String compact = display.replace(" ", "");
                if (compact.regionMatches(true, 0, "~" + profileName, 0, ("~" + profileName).length())) {
                    altered.add(profileName.toLowerCase(Locale.ROOT));
                }
            }

            this.alteredNickCache = Set.copyOf(altered);
            this.alteredNickCacheAt = refreshedAt;
            return this.alteredNickCache;
        });
    }

    @Override
    public AutoLoginResult runAutoLogin() throws Exception {
        CompletableFuture<AutoLoginResult> future = new CompletableFuture<>();
        Thread worker = new Thread(() -> {
            try {
                future.complete(doAutoLogin());
            } catch (Exception e) {
                future.completeExceptionally(e);
            }
        }, "bridge-autologin");
        worker.setDaemon(true);
        worker.start();

        try {
            return future.get(AUTOLOGIN_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new IllegalStateException("autologin_timeout");
        }
    }

    private AutoLoginResult doAutoLogin() throws Exception {
        List<String> logs = new ArrayList<>();
        List<AutoLoginStep> steps = new ArrayList<>();

        logs.add("[ml] /lite");
        sendChat("/lite");
        Thread.sleep(LITE_COMMAND_DELAY_MS);

        logs.add("[ml] ждём контейнер...");
        if (!waitUntilContainerOpen(CONTAINER_OPEN_TIMEOUT_MS)) {
            return AutoLoginResult.failure("container_not_opened", logs, steps);
        }
        logs.add("[ml] контейнер открыт");
        Thread.sleep(CONTAINER_SETTLE_MS);

        String fingerprint = fingerprintContainer();
        for (int slot = 0; slot <= 3; slot++) {
            if (slot > 0) {
                Thread.sleep(CLICK_DELAY_MS);
            }
            logs.add("[ml] клик слот " + slot);
            clickContainerSlot(slot);

            if (!waitUntilContainerChanged(fingerprint, CONTAINER_CHANGE_TIMEOUT_MS)) {
                return AutoLoginResult.failure("container_not_changed_slot_" + slot, logs, steps);
            }

            fingerprint = fingerprintContainer();
            List<ContainerSlotDump> dump = dumpContainer();
            steps.add(new AutoLoginStep(slot, dump));
            logs.add(formatDump(slot, dump));
        }

        logs.add("[ml] готово");
        return AutoLoginResult.success(logs, steps);
    }

    private String formatDump(int slot, List<ContainerSlotDump> dump) {
        StringBuilder sb = new StringBuilder();
        sb.append("[ml] дамп слот ").append(slot).append(':');
        for (ContainerSlotDump item : dump) {
            sb.append("\n  [").append(item.slot()).append("] ");
            if (item.empty()) {
                sb.append("empty");
            } else {
                sb.append(item.name()).append(" (").append(item.itemId()).append(") x").append(item.count());
            }
        }
        return sb.toString();
    }

    private boolean waitUntilContainerOpen(long timeoutMs) throws Exception {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (Boolean.TRUE.equals(runOnClientThread(this::isContainerOpenSync))) {
                return true;
            }
            Thread.sleep(POLL_INTERVAL_MS);
        }
        return false;
    }

    private boolean waitUntilContainerChanged(String previous, long timeoutMs) throws Exception {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            String current = runOnClientThread(this::fingerprintContainer);
            if (current != null && !current.equals(previous)) {
                return true;
            }
            Thread.sleep(POLL_INTERVAL_MS);
        }
        return false;
    }

    private boolean isContainerOpenSync() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            return false;
        }
        Screen screen = minecraft.screen;
        return screen instanceof AbstractContainerScreen<?>;
    }

    private String fingerprintContainer() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            return "";
        }
        Screen screen = minecraft.screen;
        if (!(screen instanceof AbstractContainerScreen<?> containerScreen)) {
            return "";
        }
        AbstractContainerMenu menu = containerScreen.getMenu();
        Inventory playerInventory = minecraft.player == null ? null : minecraft.player.getInventory();
        StringBuilder sb = new StringBuilder();
        for (Slot slot : menu.slots) {
            if (!isGuiContainerSlot(slot, playerInventory)) {
                continue;
            }
            ItemStack stack = slot.getItem();
            sb.append(slot.index)
                .append(':')
                .append(BuiltInRegistries.ITEM.getKey(stack.getItem()))
                .append('x')
                .append(stack.getCount())
                .append('|');
        }
        return sb.toString();
    }

    private List<ContainerSlotDump> dumpContainer() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            return List.of();
        }
        Screen screen = minecraft.screen;
        if (!(screen instanceof AbstractContainerScreen<?> containerScreen)) {
            return List.of();
        }
        AbstractContainerMenu menu = containerScreen.getMenu();
        Inventory playerInventory = minecraft.player == null ? null : minecraft.player.getInventory();
        List<ContainerSlotDump> result = new ArrayList<>();
        for (Slot slot : menu.slots) {
            if (!isGuiContainerSlot(slot, playerInventory)) {
                continue;
            }
            ItemStack stack = slot.getItem();
            String itemId = BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
            String name = stack.isEmpty() ? "" : stack.getHoverName().getString();
            result.add(new ContainerSlotDump(
                slot.getContainerSlot(),
                itemId,
                stack.getCount(),
                name,
                stack.isEmpty()
            ));
        }
        return result;
    }

    private void clickContainerSlot(int containerSlot) throws Exception {
        runOnClientThread(() -> {
            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft.player == null || minecraft.gameMode == null) {
                throw new IllegalStateException("not_in_world");
            }
            Screen screen = minecraft.screen;
            if (!(screen instanceof AbstractContainerScreen<?> gui)) {
                throw new IllegalStateException("no_container");
            }
            AbstractContainerMenu menu = gui.getMenu();
            Inventory playerInventory = minecraft.player.getInventory();
            int menuSlotId = resolveMenuSlotIndex(menu, playerInventory, containerSlot);
            if (menuSlotId < 0) {
                throw new IllegalStateException("bad_slot_" + containerSlot);
            }

            clearCarriedItem(minecraft, menu);

            minecraft.gameMode.handleInventoryMouseClick(
                menu.containerId,
                menuSlotId,
                0,
                ClickType.THROW,
                minecraft.player
            );
        });
    }

    private int resolveMenuSlotIndex(
        AbstractContainerMenu menu,
        Inventory playerInventory,
        int containerSlot
    ) {
        for (Slot slot : menu.slots) {
            if (isGuiContainerSlot(slot, playerInventory) && slot.getContainerSlot() == containerSlot) {
                return slot.index;
            }
        }
        return -1;
    }

    private void clearCarriedItem(Minecraft minecraft, AbstractContainerMenu menu) {
        if (menu.getCarried().isEmpty()) {
            return;
        }
        minecraft.gameMode.handleInventoryMouseClick(
            menu.containerId,
            OUTSIDE_SLOT,
            0,
            ClickType.PICKUP,
            minecraft.player
        );
    }

    private boolean isGuiContainerSlot(Slot slot, Inventory playerInventory) {
        return playerInventory != null && slot.container != playerInventory;
    }

    private <T> T runOnClientThread(ThrowingSupplier<T> action) throws Exception {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            throw new IllegalStateException("minecraft_unavailable");
        }

        if (minecraft.isSameThread()) {
            return action.get();
        }

        CompletableFuture<T> future = new CompletableFuture<>();
        minecraft.execute(() -> {
            try {
                future.complete(action.get());
            } catch (Exception e) {
                future.completeExceptionally(e);
            }
        });

        try {
            return future.get(ACTION_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new IllegalStateException("client_action_timeout");
        }
    }

    private void runOnClientThread(ThrowingRunnable action) throws Exception {
        runOnClientThread(() -> {
            action.run();
            return null;
        });
    }

    @FunctionalInterface
    private interface ThrowingSupplier<T> {
        T get() throws Exception;
    }

    @FunctionalInterface
    private interface ThrowingRunnable {
        void run() throws Exception;
    }
}
