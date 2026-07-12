package net.llm.screenshotbridge.v1_20_1.mixins;

import com.mojang.blaze3d.vertex.PoseStack;
import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.EntityRenderDispatcher;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(EntityRenderDispatcher.class)
public class MixinEntityRenderDispatcher {

    @Inject(
        method = "render",
        at = @At("HEAD"),
        cancellable = true
    )
    private <E extends Entity> void screenshotbridge$skipEntityRender(
        E entity,
        double x,
        double y,
        double z,
        float rotationYaw,
        float partialTicks,
        PoseStack poseStack,
        MultiBufferSource bufferSource,
        int packedLight,
        CallbackInfo ci
    ) {
        if (CutdownModeState.isActive()) {
            ci.cancel();
        }
    }
}
