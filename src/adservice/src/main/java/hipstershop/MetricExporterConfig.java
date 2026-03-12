package hipstershop;

import io.opentelemetry.exporter.otlp.metrics.OtlpGrpcMetricExporter;
import io.opentelemetry.sdk.metrics.export.MetricExporter;

public class MetricExporterConfig {

    public static MetricExporter otlpGrpcMetricExporter(String endpoint) {
        return OtlpGrpcMetricExporter.builder()
                .setEndpoint("http://"+endpoint)
                .build();
    }

}