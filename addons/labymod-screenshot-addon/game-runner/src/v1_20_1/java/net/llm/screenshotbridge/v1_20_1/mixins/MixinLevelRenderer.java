package net.llm.screenshotbridge.v1_20_1.mixins;

import com.mojang.blaze3d.vertex.PoseStack;
import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.Camera;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.LightTexture;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(LevelRenderer.class)
public class MixinLevelRenderer {

    @Inject(
        method = "renderLevel",
        at = @At("HEAD"),
        cancellable = true
    )
    private void screenshotbridge$skipWorldRender(
        PoseStack poseStack,
        float partialTick,
        long finishNanoTime,
        boolean renderBlockOutline,
        Camera camera,
        GameRenderer gameRenderer,
        LightTexture lightTexture,
        Matrix4f projectionMatrix,
        CallbackInfo ci
    ) {
        if (CutdownModeState.isActive()) {
            ci.cancel();
        }
    }
}
