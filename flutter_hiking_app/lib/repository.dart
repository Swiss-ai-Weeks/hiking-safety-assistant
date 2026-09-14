import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'dart:convert';
import 'models.dart';
import 'sqlite_helper.dart';

class SwissHikingRepository implements HikingRepository {
  final http.Client _client;

  SwissHikingRepository({http.Client? client}) : _client = client ?? http.Client();

  @override
  Future<List<HikingRoute>> loadRoutes() async {
    // In production, fetch from MeteoSwiss and swisstopo Open Data APIs
    // For now, return sample Swiss routes
    return [
      HikingRoute(
        id: 'route_1',
        name: 'Hardergrat',
        difficulty: 'hard',
        lengthKm: 5.2,
        trailType: 'ridge',
      ),
      HikingRoute(
        id: 'route_2',
        name: 'Eiger Trail',
        difficulty: 'moderate',
        lengthKm: 9.7,
        trailType: 'trail',
      ),
      HikingRoute(
        id: 'route_3',
        name: 'Weggli',
        difficulty: 'easy',
        lengthKm: 3.5,
        trailType: 'alpine',
      ),
    ];
  }

  @override
  Future<RouteWeather> getWeather(HikingRoute route) async {
    // Fetch from MeteoSwiss Open Data
    final uri = Uri.https('api.meteoswiss.admin.ch', '/v1/forecast', {
      'route': route.id,
      'format': 'json',
    });
    final response = await _client.get(uri);
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return RouteWeather(
        temperatureC: (data['temperature'] ?? 10.0).toDouble(),
        precipitationMm: (data['precipitation'] ?? 0.0).toDouble(),
        condition: data['condition'] ?? 'Unknown',
        forecast: data['forecast'] ?? 'No forecast',
      );
    }
    // Return default if API unavailable
    return RouteWeather(
      temperatureC: 10.0,
      precipitationMm: 0.0,
      condition: 'Unknown',
      forecast: 'Unable to fetch forecast',
    );
  }

  @override
  Future<RiskAssessment> assessRisk(
      HikingRoute route, RouteWeather weather) async {
    final warnings = <String>[];
    double riskScore = 0.0;

    // Risk logic based on weather and route difficulty
    if (weather.temperatureC < 0) {
      warnings.add('Freezing temperatures expected');
      riskScore += 0.3;
    }
    if (weather.precipitationMm > 5) {
      warnings.add('Heavy precipitation forecast');
      riskScore += 0.3;
    }
    if (route.difficulty == 'hard' && weather.windSpeedKmh > 50) {
      warnings.add('High wind on exposed ridge');
      riskScore += 0.2;
    }

    String recommendation = 'Proceed with caution';
    if (riskScore > 0.6) {
      recommendation = 'Consider postponing';
    } else if (riskScore > 0.3) {
      recommendation = 'Monitor conditions closely';
    }

    return RiskAssessment(
      riskScore: min(riskScore, 1.0),
      warnings: warnings,
      recommendation: recommendation,
    );
  }
}