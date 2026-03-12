package hipstershop;

import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;

public class SdkTracerProviderConfig {
  public static SdkTracerProvider create(Resource resource) {
    return SdkTracerProvider.builder()
        .setResource(resource)
        .addSpanProcessor(
            SpanProcessorConfig.batchSpanProcessor(
                SpanExporterConfig.otlpGrpcSpanExporter(AdService.COLLECTOR_SERVICE_ADDR)))
        .setSampler(SamplerConfig.parentAndTraceIdRatioBasedSampler(0.05))
        .setSpanLimits(SpanLimitsConfig::spanLimits)
        .build();
  }
}