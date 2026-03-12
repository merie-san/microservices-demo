package hipstershop;

import io.opentelemetry.sdk.trace.SpanLimits;

public class SpanLimitsConfig {
  public static SpanLimits spanLimits() {
    return SpanLimits.builder()
        .build();
  }
}
