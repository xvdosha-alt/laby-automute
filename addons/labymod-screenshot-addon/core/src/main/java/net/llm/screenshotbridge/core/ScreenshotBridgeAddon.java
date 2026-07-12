package net.llm.screenshotbridge.core;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.List;
import java.util.function.Consumer;
import net.labymod.api.addon.LabyAddon;
import net.labymod.api.models.addon.annotation.AddonMain;
import net.llm.screenshotbridge.api.AutoLoginResult;
import net.llm.screenshotbridge.api.BridgePlayer;
import net.llm.screenshotbridge.api.CutdownModeController;
import net.llm.screenshotbridge.api.ScreenshotCapture;
import net.llm.screenshotbridge.api.generated.ReferenceStorage;

@AddonMain
public class ScreenshotBridgeAddon extends LabyAddon<ScreenshotBridgeConfiguration> {

    private static final Gson GSON = new Gson();

    private ScreenshotCapture screenshotCapture;
    private BridgePlayer bridgePlayer;
    private CutdownModeController cutdownModeController;
    private CutdownModeListener cutdownModeListener;
    private ScreenshotServer server;
    private ChatBuffer chatBuffer;
    private final long bootId = System.currentTimeMillis();
    private volatile int activePort = -1;

    @Override
    protected void enable() {
        ReferenceStorage references = (ReferenceStorage) this.referenceStorageAccessor();
        this.screenshotCapture = references.screenshotCapture();
        this.bridgePlayer = references.bridgePlayer();
        this.cutdownModeController = references.cutdownModeController();
        this.screenshotCapture.setPauseOnLostFocus(false);

        this.chatBuffer = new ChatBuffer();
        Consumer<String> mlLogger = line -> this.logger().info(line);
        this.registerListener(new ChatCaptureListener(this.chatBuffer, this.bridgePlayer));
        this.registerListener(new MlChatSendListener(this.bridgePlayer, mlLogger));
        this.registerCommand(new MlCommand(this.bridgePlayer, mlLogger));
        this.cutdownModeListener = new CutdownModeListener(
            () -> this.configuration().cutdownToggleKey().get(),
            this.cutdownModeController
        );
        this.registerListener(this.cutdownModeListener);
        ChatAnimationDisabler.apply();
        this.registerListener(new ChatFadeGuard());

        BridgeConfig config = BridgeConfig.load();
        this.server = new ScreenshotServer(config, this::handleRequest, port -> {
            this.activePort = port;
            this.logger().info("Screenshot bridge listening on {}:{}", config.host(), port);
        });
        this.server.start();
    }

    @Override
    protected Class<ScreenshotBridgeConfiguration> configurationClass() {
        return ScreenshotBridgeConfiguration.class;
    }

    private String handleRequest(String requestLine) {
        JsonObject request;
        try {
            request = JsonParser.parseString(requestLine).getAsJsonObject();
        } catch (Exception e) {
            return error("invalid_json");
        }

        String cmd = getString(request, "cmd");
        if (cmd == null || cmd.isBlank()) {
            return error("missing_cmd");
        }

        return switch (cmd) {
            case "screenshot" -> handleScreenshot(request);
            case "nick" -> handleNick();
            case "say" -> handleSay(request);
            case "chat" -> handleChat(request);
            case "online" -> handleOnline();
            case "autologin" -> handleAutoLogin();
            case "cutdown" -> handleCutdown(request);
            default -> error("unknown_cmd");
        };
    }

    private String handleScreenshot(JsonObject request) {
        String path = getString(request, "path");
        if (path == null || path.isBlank()) {
            return error("missing_path");
        }

        String format = getString(request, "format");
        if (format == null || format.isBlank()) {
            format = path.toLowerCase().endsWith(".png") ? "png" : "jpg";
        }

        if (!this.screenshotCapture.isInWorld()) {
            return error("not_in_world");
        }

        try {
            ScreenshotCapture.CaptureResult result = this.screenshotCapture.capture(path, format);
            JsonObject response = new JsonObject();
            response.addProperty("ok", true);
            response.addProperty("path", result.path());
            response.addProperty("width", result.width());
            response.addProperty("height", result.height());
            return GSON.toJson(response);
        } catch (Exception e) {
            this.logger().error("Screenshot capture failed", e);
            return error(e.getMessage() == null ? "capture_failed" : e.getMessage());
        }
    }

    private String handleNick() {
        String nick = this.bridgePlayer.getLocalNickname();
        if (nick == null || nick.isBlank()) {
            return error("not_in_world");
        }

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("nick", nick);
        response.addProperty("in_world", this.bridgePlayer.isInWorld());
        response.addProperty("port", this.activePort);
        return GSON.toJson(response);
    }

    private String handleSay(JsonObject request) {
        String targetNick = getString(request, "nick");
        String message = getString(request, "message");
        if (targetNick == null || targetNick.isBlank()) {
            return error("missing_nick");
        }
        if (message == null || message.isBlank()) {
            return error("missing_message");
        }

        String localNick = this.bridgePlayer.getLocalNickname();
        if (localNick == null || localNick.isBlank()) {
            return error("not_in_world");
        }

        if (!localNick.equalsIgnoreCase(targetNick)) {
            JsonObject response = new JsonObject();
            response.addProperty("ok", true);
            response.addProperty("sent", false);
            response.addProperty("nick", localNick);
            response.addProperty("reason", "nick_mismatch");
            return GSON.toJson(response);
        }

        try {
            this.bridgePlayer.sendChat(message);
            JsonObject response = new JsonObject();
            response.addProperty("ok", true);
            response.addProperty("sent", true);
            response.addProperty("nick", localNick);
            return GSON.toJson(response);
        } catch (Exception e) {
            this.logger().error("Chat send failed", e);
            return error(e.getMessage() == null ? "send_failed" : e.getMessage());
        }
    }

    private String handleChat(JsonObject request) {
        int since = 0;
        if (request.has("since") && !request.get("since").isJsonNull()) {
            since = request.get("since").getAsInt();
        }

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("last", this.chatBuffer.lastSeq());
        response.addProperty("boot", this.bootId);
        response.addProperty("port", this.activePort);
        response.addProperty("in_world", this.bridgePlayer.isInWorld());
        String localNick = this.bridgePlayer.getLocalNickname();
        if (localNick != null && !localNick.isBlank()) {
            response.addProperty("nick", localNick);
        }

        if (since < 0) {
            return GSON.toJson(response);
        }

        JsonArray messages = new JsonArray();
        for (ChatBuffer.Entry entry : this.chatBuffer.pollSince(since)) {
            JsonObject item = new JsonObject();
            item.addProperty("seq", entry.seq());
            item.addProperty("time", entry.time());
            item.addProperty("nick", entry.nick());
            item.addProperty("text", entry.text());
            item.addProperty("altered", entry.alteredNick());
            messages.add(item);
        }
        response.add("messages", messages);
        return GSON.toJson(response);
    }

    private String handleOnline() {
        if (!this.bridgePlayer.isInWorld()) {
            return error("not_in_world");
        }

        List<String> players;
        try {
            players = this.bridgePlayer.getOnlinePlayerNicks();
        } catch (Exception e) {
            this.logger().error("Online players query failed", e);
            return error(e.getMessage() == null ? "online_failed" : e.getMessage());
        }

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("count", players.size());
        response.addProperty("port", this.activePort);

        JsonArray nicks = new JsonArray();
        for (String nick : players) {
            nicks.add(nick);
        }
        response.add("players", nicks);
        return GSON.toJson(response);
    }

    private String handleCutdown(JsonObject request) {
        String mode = getString(request, "mode");
        if (mode == null || mode.isBlank() || mode.equalsIgnoreCase("toggle")) {
            this.cutdownModeListener.toggle();
        } else if (mode.equalsIgnoreCase("on") || mode.equalsIgnoreCase("true")) {
            this.cutdownModeListener.setEnabled(true);
        } else if (mode.equalsIgnoreCase("off") || mode.equalsIgnoreCase("false")) {
            this.cutdownModeListener.setEnabled(false);
        } else {
            return error("invalid_mode");
        }

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("active", CutdownModeState.isActive());
        return GSON.toJson(response);
    }

    private String handleAutoLogin() {
        if (!this.bridgePlayer.isInWorld()) {
            return error("not_in_world");
        }

        try {
            AutoLoginResult result = this.bridgePlayer.runAutoLogin();
            AutoLoginSupport.logResult(result, line -> this.logger().info(line));
            JsonObject response = AutoLoginSupport.toJson(result);
            response.addProperty("ok", true);
            return GSON.toJson(response);
        } catch (Exception e) {
            this.logger().error("AutoLogin failed", e);
            return error(e.getMessage() == null ? "autologin_failed" : e.getMessage());
        }
    }

    private static String getString(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return null;
        }
        return object.get(key).getAsString();
    }

    private static String error(String message) {
        JsonObject response = new JsonObject();
        response.addProperty("ok", false);
        response.addProperty("error", message);
        return GSON.toJson(response);
    }
}
