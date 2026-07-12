package net.llm.screenshotbridge.core;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.function.Consumer;
import net.llm.screenshotbridge.api.AutoLoginResult;
import net.llm.screenshotbridge.api.AutoLoginStep;
import net.llm.screenshotbridge.api.ContainerSlotDump;

public final class AutoLoginSupport {

    private AutoLoginSupport() {
    }

    public static void logResult(AutoLoginResult result, Consumer<String> logger) {
        for (String line : result.logs()) {
            logger.accept(line);
        }
        if (!result.ok()) {
            logger.accept("[ml] провал: " + result.error());
        }
    }

    public static JsonObject toJson(AutoLoginResult result) {
        JsonObject response = new JsonObject();
        response.addProperty("success", result.ok());
        if (!result.error().isBlank()) {
            response.addProperty("error", result.error());
        }

        JsonArray logs = new JsonArray();
        for (String line : result.logs()) {
            logs.add(line);
        }
        response.add("logs", logs);

        JsonArray steps = new JsonArray();
        for (AutoLoginStep step : result.steps()) {
            JsonObject item = new JsonObject();
            item.addProperty("slot", step.slot());
            JsonArray slots = new JsonArray();
            for (ContainerSlotDump dump : step.slots()) {
                JsonObject slot = new JsonObject();
                slot.addProperty("slot", dump.slot());
                slot.addProperty("id", dump.itemId());
                slot.addProperty("count", dump.count());
                slot.addProperty("empty", dump.empty());
                if (dump.name() != null && !dump.name().isBlank()) {
                    slot.addProperty("name", dump.name());
                }
                slots.add(slot);
            }
            item.add("slots", slots);
            steps.add(item);
        }
        response.add("steps", steps);
        return response;
    }
}
