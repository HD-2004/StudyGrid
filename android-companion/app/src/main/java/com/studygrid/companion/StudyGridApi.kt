package com.studygrid.companion

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate

data class PairingResult(val planId: String, val accessToken: String)

data class HealthDailyAggregate(
    val date: LocalDate,
    val sleepMinutes: Long?,
    val sleepStart: String?,
    val sleepEnd: String?,
    val restingHeartRate: Double?,
    val hrvRmssd: Double?,
    val sources: Set<String>,
)

class StudyGridApi {
    suspend fun claim(serverUrl: String, code: String): PairingResult = withContext(Dispatchers.IO) {
        val response = post(
            serverUrl,
            "/api/health/pairing/claim",
            JSONObject().put("code", code),
            token = null,
        )
        PairingResult(
            planId = response.getString("plan_id"),
            accessToken = response.getString("access_token"),
        )
    }

    suspend fun sync(
        serverUrl: String,
        token: String,
        summaries: List<HealthDailyAggregate>,
        permissions: Set<String>,
    ): Int = withContext(Dispatchers.IO) {
        val devices = summaries.flatMap { it.sources }.distinct().sorted()
        val payload = JSONObject()
            .put("permissions", JSONArray(permissions.sorted()))
            .put("sources", JSONArray(devices))
            .put("summaries", JSONArray().apply {
                summaries.forEach { summary ->
                    put(JSONObject().apply {
                        put("occurred_on", summary.date.toString())
                        putNullable("sleep_minutes", summary.sleepMinutes)
                        putNullable("sleep_start", summary.sleepStart)
                        putNullable("sleep_end", summary.sleepEnd)
                        putNullable("resting_heart_rate_bpm", summary.restingHeartRate)
                        putNullable("hrv_rmssd_ms", summary.hrvRmssd)
                        put("source_devices", JSONArray(summary.sources.sorted()))
                    })
                }
            })
        post(serverUrl, "/api/health/sync", payload, token).getInt("accepted_days")
    }

    private fun JSONObject.putNullable(name: String, value: Any?) {
        put(name, value ?: JSONObject.NULL)
    }

    private fun post(
        serverUrl: String,
        path: String,
        payload: JSONObject,
        token: String?,
    ): JSONObject {
        val base = serverUrl.trim().trimEnd('/')
        require(base.startsWith("https://") || (BuildConfig.DEBUG && base.startsWith("http://"))) {
            "Use an HTTPS StudyGrid address. Debug builds also allow a local HTTP address."
        }
        val connection = URL("$base$path").openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 12_000
            connection.readTimeout = 20_000
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "application/json")
            if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
            connection.outputStream.bufferedWriter().use { it.write(payload.toString()) }
            val status = connection.responseCode
            val body = (if (status in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (status !in 200..299) {
                val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull()
                error(detail?.takeIf { it.isNotBlank() } ?: "StudyGrid returned HTTP $status")
            }
            JSONObject(body)
        } finally {
            connection.disconnect()
        }
    }
}
