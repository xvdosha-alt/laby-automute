package net.llm.screenshotbridge.v1_20_1;

import net.labymod.api.models.Implements;
import net.llm.screenshotbridge.api.CutdownModeController;
import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientChunkCache;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.network.chat.Component;

@Implements(CutdownModeController.class)
public class VersionedCutdownModeController implements CutdownModeController {

    private static final int DROP_SCAN_RADIUS = 32;
    private static final double MIN_ENTITY_DISTANCE = 0.5D;

    @Override
    public boolean isInWorld() {
        Minecraft minecraft = Minecraft.getInstance();
        return minecraft != null && minecraft.player != null && minecraft.level != null;
    }

    @Override
    public void captureFrozenPose() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null) {
            return;
        }

        CutdownModeState.setFrozenPose(
            minecraft.player.getX(),
            minecraft.player.getY(),
            minecraft.player.getZ(),
            minecraft.player.getYRot(),
            minecraft.player.getXRot()
        );
    }

    @Override
    public void applyMemoryCuts() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null || minecraft.level == null || minecraft.options == null) {
            return;
        }

        var options = minecraft.options;
        CutdownModeState.setSavedMemorySettings(new CutdownModeState.SavedMemorySettings(
            options.renderDistance().get(),
            options.simulationDistance().get(),
            options.entityDistanceScaling().get()
        ));

        int keepRadius = CutdownModeState.getChunkKeepRadius();
        options.renderDistance().set(keepRadius);
        options.simulationDistance().set(keepRadius);
        options.entityDistanceScaling().set(MIN_ENTITY_DISTANCE);
        options.graphicsMode().set(net.minecraft.client.GraphicsStatus.FAST);
        options.cloudStatus().set(net.minecraft.client.CloudStatus.OFF);
        options.ambientOcclusion().set(false);

        int centerX = minecraft.player.chunkPosition().x;
        int centerZ = minecraft.player.chunkPosition().z;
        ClientChunkCache chunkSource = ((ClientLevel) minecraft.level).getChunkSource();
        chunkSource.updateViewCenter(centerX, centerZ);
        chunkSource.updateViewRadius(keepRadius);
        dropDistantChunks(chunkSource, centerX, centerZ, keepRadius);

        if (minecraft.levelRenderer != null) {
            minecraft.levelRenderer.clear();
        }
    }

    @Override
    public void restoreMemorySettings() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.options == null) {
            return;
        }

        CutdownModeState.SavedMemorySettings saved = CutdownModeState.getSavedMemorySettings();
        if (saved != null) {
            var options = minecraft.options;
            options.renderDistance().set(saved.renderDistance());
            options.simulationDistance().set(saved.simulationDistance());
            options.entityDistanceScaling().set(saved.entityDistanceScaling());
        }
        CutdownModeState.setSavedMemorySettings(null);

        if (minecraft.player != null && minecraft.level != null) {
            int centerX = minecraft.player.chunkPosition().x;
            int centerZ = minecraft.player.chunkPosition().z;
            ClientChunkCache chunkSource = ((ClientLevel) minecraft.level).getChunkSource();
            chunkSource.updateViewCenter(centerX, centerZ);
            if (saved != null) {
                chunkSource.updateViewRadius(saved.renderDistance());
            }
        }

        if (minecraft.levelRenderer != null) {
            minecraft.levelRenderer.allChanged();
        }
    }

    @Override
    public void notifyToggled(boolean enabled) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player == null) {
            return;
        }

        String message = enabled
            ? "§a[Cutdown] §7рендер выкл, чанки урезаны до "
                + CutdownModeState.getChunkKeepRadius()
                + ", память должна упасть через несколько сек"
            : "§c[Cutdown] §7выключено, настройки и мир восстановлены";
        minecraft.player.displayClientMessage(Component.literal(message), true);
    }

    public static void dropDistantChunks(ClientChunkCache chunkSource, int centerX, int centerZ, int keepRadius) {
        for (int dx = -DROP_SCAN_RADIUS; dx <= DROP_SCAN_RADIUS; dx++) {
            for (int dz = -DROP_SCAN_RADIUS; dz <= DROP_SCAN_RADIUS; dz++) {
                if (Math.max(Math.abs(dx), Math.abs(dz)) <= keepRadius) {
                    continue;
                }
                chunkSource.drop(centerX + dx, centerZ + dz);
            }
        }
    }
}
