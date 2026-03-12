package hipstershop;
import io.opentelemetry.sdk.trace.samplers.Sampler;

public class SamplerConfig {

  public static Sampler parentAndTraceIdRatioBasedSampler(double ratio) {
    return Sampler.parentBasedBuilder(Sampler.traceIdRatioBased(ratio))
        .build();
  }


}