package net.llm.screenshotbridge.core;

import java.util.function.Supplier;
import net.labymod.api.client.gui.screen.key.Key;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.input.KeyEvent;
import net.llm.screenshotbridge.api.CutdownModeController;

public class CutdownModeListener {

    private static final Key[] MOVEMENT_KEYS = {
        Key.W, Key.A, Key.S, Key.D,
        Key.SPACE, Key.L_SHIFT, Key.R_SHIFT,
        Key.ARROW_UP, Key.ARROW_DOWN, Key.ARROW_LEFT, Key.ARROW_RIGHT
    };

    private final Supplier<Key> toggleKey;
    private final CutdownModeController controller;

    public CutdownModeListener(Supplier<Key> toggleKey, CutdownModeController controller) {
        this.toggleKey = toggleKey;
        this.controller = controller;
    }

    @Subscribe
    public void onToggleKey(KeyEvent event) {
        if (event.state() != KeyEvent.State.PRESS) {
            return;
        }

        Key bind = this.toggleKey.get();
        if (bind == null || bind.isUnknown() || bind == Key.NONE) {
            return;
        }
        if (!event.key().equals(bind)) {
            return;
        }

        toggle();
    }

    @Subscribe
    public void onMovementKey(KeyEvent event) {
        if (!CutdownModeState.isActive()) {
            return;
        }
        if (event.state() == KeyEvent.State.UNPRESSED) {
            return;
        }

        for (Key movementKey : MOVEMENT_KEYS) {
            if (event.key().equals(movementKey)) {
                event.setCancelled(true);
                return;
            }
        }
    }

    public void toggle() {
        if (!this.controller.isInWorld()) {
            return;
        }

        boolean next = !CutdownModeState.isActive();
        if (next) {
            this.controller.captureFrozenPose();
            if (CutdownModeState.getFrozenPose() == null) {
                return;
            }
            CutdownModeState.setActive(true);
            this.controller.applyMemoryCuts();
            this.controller.notifyToggled(true);
            return;
        }

        CutdownModeState.setActive(false);
        this.controller.restoreMemorySettings();
        this.controller.notifyToggled(false);
    }

    public void setEnabled(boolean enabled) {
        if (enabled == CutdownModeState.isActive()) {
            return;
        }
        toggle();
    }
}
