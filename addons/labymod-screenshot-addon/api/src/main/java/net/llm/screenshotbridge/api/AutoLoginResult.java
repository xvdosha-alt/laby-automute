package net.llm.screenshotbridge.api;

import java.util.List;

public final class AutoLoginResult {

    private final boolean ok;
    private final String error;
    private final List<String> logs;
    private final List<AutoLoginStep> steps;

    public AutoLoginResult(boolean ok, String error, List<String> logs, List<AutoLoginStep> steps) {
        this.ok = ok;
        this.error = error == null ? "" : error;
        this.logs = List.copyOf(logs);
        this.steps = List.copyOf(steps);
    }

    public static AutoLoginResult success(List<String> logs, List<AutoLoginStep> steps) {
        return new AutoLoginResult(true, "", logs, steps);
    }

    public static AutoLoginResult failure(String error, List<String> logs, List<AutoLoginStep> steps) {
        return new AutoLoginResult(false, error, logs, steps);
    }

    public boolean ok() {
        return ok;
    }

    public String error() {
        return error;
    }

    public List<String> logs() {
        return logs;
    }

    public List<AutoLoginStep> steps() {
        return steps;
    }
}
