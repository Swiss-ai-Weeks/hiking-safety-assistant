@immutable
abstract class HikingRepository {
  /// Load Swiss hiking routes from Open Data
  Future<List<HikingRoute>> loadRoutes();

  /// Get current/forecast weather for a route
  Future<RouteWeather> getWeather(HikingRoute route);

  /// Assess risk level for a planned hike
  Future<RiskAssessment> assessRisk(HikingRoute route, RouteWeather weather);
}

@immutable
class HikingRoute {
  final String id;
  final String name;
  final String difficulty;
  final double lengthKm;
  final String trailType;

  HikingRoute({
    required this.id,
    required this.name,
    required this.difficulty,
    required this.lengthKm,
    required this.trailType,
  });
}

@immutable
class RouteWeather {
  final double temperatureC;
  final double precipitationMm;
  final String condition;
  final String forecast;

  RouteWeather({
    required this.temperatureC,
    this.precipitationMm = 0.0,
    required this.condition,
    required this.forecast,
  });
}

@immutable
class RiskAssessment {
  final double riskScore; // 0.0-1.0
  final List<String> warnings;
  final String recommendation;

  const RiskAssessment({
    required this.riskScore,
    required this.warnings,
    required this.recommendation,
  });
}