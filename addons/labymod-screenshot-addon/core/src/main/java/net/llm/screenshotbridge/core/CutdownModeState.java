package net.llm.screenshotbridge.core;

public final class CutdownModeState {

    public static final int CHUNK_KEEP_RADIUS = 2;

    private static volatile boolean active;
    private static volatile FrozenPose frozenPose;
    private static volatile SavedMemorySettings savedMemorySettings;

    private CutdownModeState() {
    }

    public static boolean isActive() {
        return active;
    }

    public static int getChunkKeepRadius() {
        return CHUNK_KEEP_RADIUS;
    }

    public static void setActive(boolean value) {
        active = value;
        if (!value) {
            frozenPose = null;
        }
    }

    public static FrozenPose getFrozenPose() {
        return frozenPose;
    }

    public static void setFrozenPose(double x, double y, double z, float yaw, float pitch) {
        frozenPose = new FrozenPose(x, y, z, yaw, pitch);
    }

    public static SavedMemorySettings getSavedMemorySettings() {
        return savedMemorySettings;
    }

    public static void setSavedMemorySettings(SavedMemorySettings settings) {
        savedMemorySettings = settings;
    }

    public record FrozenPose(double x, double y, double z, float yaw, float pitch) {
    }

    public record SavedMemorySettings(
        int renderDistance,
        int simulationDistance,
        double entityDistanceScaling
    ) {
    }
}
