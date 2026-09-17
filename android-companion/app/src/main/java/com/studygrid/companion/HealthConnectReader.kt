package com.studygrid.companion

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateVariabilityRmssdRecord
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

class HealthConnectReader(private val context: Context) {
    private val client by lazy { HealthConnectClient.getOrCreate(context) }

    val corePermissions: Set<String> = setOf(
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(RestingHeartRateRecord::class),
        HealthPermission.getReadPermission(HeartRateVariabilityRmssdRecord::class),
    )

    val requestedPermissions: Set<String> = corePermissions +
        HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND

    fun sdkStatus(): Int = HealthConnectClient.getSdkStatus(context)

    suspend fun grantedPermissions(): Set<String> =
        client.permissionController.getGrantedPermissions()

    suspend fun hasCorePermissions(): Boolean = grantedPermissions().containsAll(corePermissions)

    suspend fun hasBackgroundPermission(): Boolean =
        HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND in grantedPermissions()

    suspend fun readDaily(days: Int = 7): List<HealthDailyAggregate> {
        require(days in 1..30)
        check(hasCorePermissions()) { "Health Connect permissions have not been granted." }
        val zone = ZoneId.systemDefault()
        val end = Instant.now()
        val start = LocalDate.now(zone).minusDays((days - 1).toLong())
            .atStartOfDay(zone).toInstant()
        val filter = TimeRangeFilter.between(start, end)
        val sleepRecords = client.readRecords(
            ReadRecordsRequest(SleepSessionRecord::class, timeRangeFilter = filter),
        ).records
        val heartRecords = client.readRecords(
            ReadRecordsRequest(RestingHeartRateRecord::class, timeRangeFilter = filter),
        ).records
        val hrvRecords = client.readRecords(
            ReadRecordsRequest(HeartRateVariabilityRmssdRecord::class, timeRangeFilter = filter),
        ).records

        val dates = (0 until days).map { LocalDate.now(zone).minusDays((days - 1 - it).toLong()) }
        return dates.mapNotNull { day ->
            val sleeps = sleepRecords.filter { it.endTime.atZone(zone).toLocalDate() == day }
            val hearts = heartRecords.filter { it.time.atZone(zone).toLocalDate() == day }
            val hrvs = hrvRecords.filter { it.time.atZone(zone).toLocalDate() == day }
            if (sleeps.isEmpty() && hearts.isEmpty() && hrvs.isEmpty()) return@mapNotNull null
            val sources = buildSet {
                sleeps.forEach { add(it.metadata.dataOrigin.packageName) }
                hearts.forEach { add(it.metadata.dataOrigin.packageName) }
                hrvs.forEach { add(it.metadata.dataOrigin.packageName) }
            }
            HealthDailyAggregate(
                date = day,
                sleepMinutes = sleeps.takeIf { it.isNotEmpty() }
                    ?.sumOf { Duration.between(it.startTime, it.endTime).toMinutes() },
                sleepStart = sleeps.minByOrNull { it.startTime }?.startTime?.toString(),
                sleepEnd = sleeps.maxByOrNull { it.endTime }?.endTime?.toString(),
                restingHeartRate = hearts.takeIf { it.isNotEmpty() }
                    ?.map { it.beatsPerMinute.toDouble() }?.average(),
                hrvRmssd = hrvs.takeIf { it.isNotEmpty() }
                    ?.map { it.heartRateVariabilityMillis }?.average(),
                sources = sources,
            )
        }
    }
}
