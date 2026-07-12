package net.llm.screenshotbridge.v1_20_1.mixins;

import net.llm.screenshotbridge.core.CutdownModeState;
import net.minecraft.client.player.Input;
import net.minecraft.client.player.LocalPlayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(LocalPlayer.class)
public abstract class MixinLocalPlayer {

    @Shadow
    public Input input;

    @Inject(method = "tick", at = @At("HEAD"))
    private void screenshotbridge$freezeMovement(CallbackInfo ci) {
        if (!CutdownModeState.isActive()) {
            return;
        }

        CutdownModeState.FrozenPose pose = CutdownModeState.getFrozenPose();
        if (pose == null) {
            return;
        }

        LocalPlayer self = (LocalPlayer) (Object) this;
        self.setPos(pose.x(), pose.y(), pose.z());
        self.setYRot(pose.yaw());
        self.setXRot(pose.pitch());
        self.setDeltaMovement(0.0D, 0.0D, 0.0D);
        self.xo = pose.x();
        self.yo = pose.y();
        self.zo = pose.z();
        self.yRotO = pose.yaw();
        self.xRotO = pose.pitch();

        if (this.input != null) {
            this.input.up = false;
            this.input.down = false;
            this.input.left = false;
            this.input.right = false;
            this.input.jumping = false;
            this.input.shiftKeyDown = false;
            this.input.forwardImpulse = 0.0F;
            this.input.leftImpulse = 0.0F;
        }
    }
}
