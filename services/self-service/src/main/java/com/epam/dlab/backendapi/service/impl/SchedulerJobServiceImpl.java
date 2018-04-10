/*
 * Copyright (c) 2018, EPAM SYSTEMS INC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.epam.dlab.backendapi.service.impl;

import com.epam.dlab.UserInstanceStatus;
import com.epam.dlab.auth.SystemUserInfoServiceImpl;
import com.epam.dlab.auth.UserInfo;
import com.epam.dlab.backendapi.dao.ComputationalDAO;
import com.epam.dlab.backendapi.dao.ExploratoryDAO;
import com.epam.dlab.backendapi.dao.SchedulerJobDAO;
import com.epam.dlab.backendapi.service.ComputationalService;
import com.epam.dlab.backendapi.service.ExploratoryService;
import com.epam.dlab.backendapi.service.SchedulerJobService;
import com.epam.dlab.dto.SchedulerJobDTO;
import com.epam.dlab.dto.UserInstanceDTO;
import com.epam.dlab.dto.computational.UserComputationalResource;
import com.epam.dlab.exceptions.ResourceInappropriateStateException;
import com.epam.dlab.exceptions.ResourceNotFoundException;
import com.epam.dlab.model.scheduler.SchedulerJobData;
import com.google.inject.Inject;
import com.google.inject.Singleton;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;

import java.time.*;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Slf4j
@Singleton
public class SchedulerJobServiceImpl implements SchedulerJobService {

	private static final String SCHEDULER_NOT_FOUND_MSG =
			"Scheduler job data not found for user %s with exploratory %s";
	private static final String CURRENT_DATETIME_INFO =
			"Current time rounded: {} , current date: {}, current day of week: {}";

	@Inject
	private SchedulerJobDAO schedulerJobDAO;

	@Inject
	private ExploratoryDAO exploratoryDAO;

	@Inject
	private ComputationalDAO computationalDAO;

	@Inject
	private ExploratoryService exploratoryService;

	@Inject
	private ComputationalService computationalService;

	@Inject
	private SystemUserInfoServiceImpl systemUserService;

	@Override
	public SchedulerJobDTO fetchSchedulerJobForUserAndExploratory(String user, String exploratoryName) {
		if (!exploratoryDAO.isExploratoryExist(user, exploratoryName)) {
			throw new ResourceNotFoundException(String.format(ExploratoryDAO.EXPLORATORY_NOT_FOUND_MSG, user,
					exploratoryName));
		}
		return schedulerJobDAO.fetchSingleSchedulerJobByUserAndExploratory(user, exploratoryName)
				.orElseThrow(() -> new ResourceNotFoundException(String.format(SCHEDULER_NOT_FOUND_MSG, user,
						exploratoryName)));
	}

	@Override
	public SchedulerJobDTO fetchSchedulerJobForComputationalResource(String user, String exploratoryName,
																	 String computationalName) {
		if (!computationalDAO.isComputationalExist(user, exploratoryName, computationalName)) {
			throw new ResourceNotFoundException(String.format(ComputationalDAO.COMPUTATIONAL_NOT_FOUND_MSG,
					computationalName, exploratoryName, user));
		}
		return schedulerJobDAO.fetchSingleSchedulerJobForCluster(user, exploratoryName, computationalName)
				.orElseThrow(() -> new ResourceNotFoundException(String.format(SCHEDULER_NOT_FOUND_MSG, user,
						exploratoryName) + "with computational resource " + computationalName));
	}

	@Override
	public void updateSchedulerDataForUserAndExploratory(String user, String exploratoryName, SchedulerJobDTO dto) {
		checkExploratoryStatusOrElseThrowException(user, exploratoryName);
		enrichSchedulerJobIfNecessary(dto);
		log.debug("Updating exploratory {} for user {} with new scheduler job data {}...",
				exploratoryName, user, dto);
		exploratoryDAO.updateSchedulerDataForUserAndExploratory(user, exploratoryName, dto);
	}

	@Override
	public void updateSchedulerDataForComputationalResource(String user, String exploratoryName,
															String computationalName, SchedulerJobDTO dto) {
		checkExploratoryStatusOrElseThrowException(user, exploratoryName);
		checkComputationalStatusOrElseThrowException(user, exploratoryName, computationalName);
		enrichSchedulerJobIfNecessary(dto);
		log.debug("Updating computational resource {} affiliated with exploratory {} for user {} with new scheduler " +
				"job data {}...", computationalName, exploratoryName, user, dto);
		computationalDAO.updateSchedulerDataForComputationalResource(user, exploratoryName, computationalName, dto);

	}

	@Override
	public void executeStartResourceJob(boolean isAppliedForClusters) {
		OffsetDateTime currentDateTime = OffsetDateTime.now();
		List<SchedulerJobData> jobsToStart =
				getSchedulerJobsForAction(UserInstanceStatus.RUNNING, currentDateTime, isAppliedForClusters);
		if (!jobsToStart.isEmpty()) {
			log.debug(isAppliedForClusters ? "Scheduler computational resource start job is executing..." :
					"Scheduler exploratory start job is executing...");
			log.info(CURRENT_DATETIME_INFO, LocalTime.of(currentDateTime.toLocalTime().getHour(),
					currentDateTime.toLocalTime().getMinute()), currentDateTime.toLocalDate(),
					currentDateTime.getDayOfWeek());
			log.info(isAppliedForClusters ? "Quantity of clusters for starting: {}" :
					"Quantity of exploratories for starting: {}", jobsToStart.size());
			jobsToStart.forEach(job -> changeResourceStatusTo(UserInstanceStatus.RUNNING, job, isAppliedForClusters));
		}

	}

	@Override
	public void executeStopResourceJob(boolean isAppliedForClusters) {
		OffsetDateTime currentDateTime = OffsetDateTime.now();
		List<SchedulerJobData> jobsToStop =
				getSchedulerJobsForAction(UserInstanceStatus.STOPPED, currentDateTime, isAppliedForClusters);
		if (!jobsToStop.isEmpty()) {
			log.debug(isAppliedForClusters ? "Scheduler computational resource stop job is executing..." :
					"Scheduler exploratory stop job is executing...");
			log.info(CURRENT_DATETIME_INFO, LocalTime.of(currentDateTime.toLocalTime().getHour(),
					currentDateTime.toLocalTime().getMinute()), currentDateTime.toLocalDate(),
					currentDateTime.getDayOfWeek());
			log.info(isAppliedForClusters ? "Quantity of clusters for stopping: {}" :
					"Quantity of exploratories for stopping: {}", jobsToStop.size());
			jobsToStop.forEach(job -> changeResourceStatusTo(UserInstanceStatus.STOPPED, job, isAppliedForClusters));
		}
	}

	@Override
	public void executeTerminateResourceJob(boolean isAppliedForClusters) {
		OffsetDateTime currentDateTime = OffsetDateTime.now();
		List<SchedulerJobData> jobsToTerminate =
				getSchedulerJobsForAction(UserInstanceStatus.TERMINATED, currentDateTime, isAppliedForClusters);
		if (!jobsToTerminate.isEmpty()) {
			log.debug(isAppliedForClusters ? "Scheduler computational resource terminate job is executing..." :
					"Scheduler exploratory terminate job is executing...");
			log.info(CURRENT_DATETIME_INFO, LocalTime.of(currentDateTime.toLocalTime().getHour(),
					currentDateTime.toLocalTime().getMinute()), currentDateTime.toLocalDate(),
					currentDateTime.getDayOfWeek());
			log.info(isAppliedForClusters ? "Quantity of clusters for terminating: {}" :
					"Quantity of exploratories for terminating: {}", jobsToTerminate.size());
			jobsToTerminate.forEach(job ->
					changeResourceStatusTo(UserInstanceStatus.TERMINATED, job, isAppliedForClusters));
		}
	}


	/**
	 * Pulls out scheduler jobs data to achieve target exploratory ('isAppliedForClusters' equals 'false') or
	 * computational ('isAppliedForClusters' equals 'true') status running/stopped/terminated.
	 *
	 * @param desiredStatus        target exploratory/cluster status (running/stopped/terminated)
	 * @param dateTime             actual date with time
	 * @param isAppliedForClusters true/false
	 * @return list of scheduler jobs data
	 */
	private List<SchedulerJobData> getSchedulerJobsToAchieveStatus(UserInstanceStatus desiredStatus,
																   OffsetDateTime dateTime,
																   boolean isAppliedForClusters) {
		return schedulerJobDAO.getSchedulerJobsToAchieveStatus(desiredStatus, dateTime, isAppliedForClusters);
	}


	/**
	 * Pulls out scheduler jobs data for the following starting/terminating/stopping corresponding exploratories
	 * ('isAppliedForClusters' equals 'false') or computational resources ('isAppliedForClusters' equals 'true').
	 *
	 * @param desiredStatus         target exploratory/cluster status (running/stopped/terminated)
	 * @param currentDateTime       actual date with time
	 * @param isAppliedForClusters  true/false
	 * @return list of scheduler jobs data
	 */
	private List<SchedulerJobData> getSchedulerJobsForAction(UserInstanceStatus desiredStatus,
															 OffsetDateTime currentDateTime,
															 boolean isAppliedForClusters) {
		switch (desiredStatus) {
			case RUNNING:
			case TERMINATED:
				return getSchedulerJobsToAchieveStatus(desiredStatus, currentDateTime, isAppliedForClusters);
			case STOPPED:
				return Stream.of(
						getSchedulerJobsToAchieveStatus(desiredStatus, currentDateTime, isAppliedForClusters)
								.stream()
								.filter(jobData -> Objects.nonNull(jobData.getJobDTO().getStartTime()) &&
										jobData.getJobDTO().getEndTime().isAfter(jobData.getJobDTO().getStartTime())),
						getSchedulerJobsToAchieveStatus(desiredStatus, currentDateTime.minusDays(1),
								isAppliedForClusters)
								.stream()
								.filter(jobData -> {
									LocalDateTime convertedDateTime = ZonedDateTime.ofInstant(currentDateTime
													.toInstant(),
											ZoneId.ofOffset(SchedulerJobDAO.TIMEZONE_PREFIX, jobData.getJobDTO()
													.getTimeZoneOffset())).toLocalDateTime();
									return Objects.nonNull(jobData.getJobDTO().getStartTime()) &&
											jobData.getJobDTO().getEndTime().isBefore(jobData.getJobDTO()
													.getStartTime())
											&& !convertedDateTime.toLocalDate().isAfter(jobData.getJobDTO()
											.getFinishDate());
								}),
						getSchedulerJobsToAchieveStatus(desiredStatus, currentDateTime, isAppliedForClusters).stream()
								.filter(jobData -> Objects.isNull(jobData.getJobDTO().getStartTime()))
				).flatMap(Function.identity()).collect(Collectors.toList());
			default:
				return Collections.emptyList();
		}
	}


	/**
	 * Starts/stops/terminates exploratory ('isAppliedForClusters' equals 'false') or computational resource
	 * ('isAppliedForClusters' equals 'true') corresponding to target status and scheduler job data.
	 *
	 * @param desiredStatus target exploratory/computational status (running/stopped/terminated)
	 * @param jobData       scheduler job data which includes exploratory details
	 */
	private void changeResourceStatusTo(UserInstanceStatus desiredStatus, SchedulerJobData jobData,
										boolean isAppliedForClusters) {
		log.debug(String.format(isAppliedForClusters ? "Computational resource " + jobData.getComputationalName() +
						" affiliated with exploratory %s and user %s is %s..." :
						"Exploratory with name %s for user %s is %s...",
				jobData.getExploratoryName(), jobData.getUser(), getActionBasedOnDesiredStatus(desiredStatus)));
		UserInfo userInfo = systemUserService.create(jobData.getUser());
		if (isAppliedForClusters) {
			executeComputationalAction(userInfo, jobData.getExploratoryName(), jobData.getComputationalName(),
					desiredStatus);
		} else {
			executeExploratoryAction(userInfo, jobData.getExploratoryName(), desiredStatus);
		}
	}


	private UserInstanceStatus getActionBasedOnDesiredStatus(UserInstanceStatus desiredStatus) {
		switch (desiredStatus) {
			case RUNNING:
				return UserInstanceStatus.STARTING;
			case STOPPED:
				return UserInstanceStatus.STOPPING;
			case TERMINATED:
				return UserInstanceStatus.TERMINATING;
			default:
				return null;
		}
	}

	private void executeExploratoryAction(UserInfo userInfo, String exploratoryName, UserInstanceStatus
			desiredStatus) {
		switch (desiredStatus) {
			case RUNNING:
				startSparkClustersWithExploratory(userInfo, exploratoryName);
				break;
			case STOPPED:
				exploratoryService.stop(userInfo, exploratoryName);
				break;
			case TERMINATED:
				exploratoryService.terminate(userInfo, exploratoryName);
				break;
			default:
				break;
		}
	}

	private void startSparkClustersWithExploratory(UserInfo userInfo, String exploratoryName) {
		exploratoryService.start(userInfo, exploratoryName);
		List<String> computationalResourcesForStartingWithExploratory =
				getComputationalResourcesForStartingWithExploratory(userInfo.getName(), exploratoryName);
		if (computationalResourcesForStartingWithExploratory.isEmpty()) {
			return;
		}
		ExecutorService executor =
				Executors.newFixedThreadPool(computationalResourcesForStartingWithExploratory.size());
		computationalResourcesForStartingWithExploratory.forEach(compName ->
				executor.execute(() -> {
							UserInfo user = systemUserService.create(userInfo.getName());
							computationalService.startSparkCluster(user, exploratoryName, compName);
						}
				));
	}

	private void executeComputationalAction(UserInfo userInfo, String exploratoryName, String computationalName,
											UserInstanceStatus desiredStatus) {
		switch (desiredStatus) {
			case RUNNING:
				computationalService.startSparkCluster(userInfo, exploratoryName, computationalName);
				break;
			case STOPPED:
				computationalService.stopSparkCluster(userInfo, exploratoryName, computationalName);
				break;
			case TERMINATED:
				computationalService.terminateComputationalEnvironment(userInfo, exploratoryName, computationalName);
				break;
			default:
				break;
		}
	}

	private List<String> getComputationalResourcesForStartingWithExploratory(String user, String exploratoryName) {
		return computationalDAO.getComputationalResourcesWithStatus(UserInstanceStatus.STOPPED, user,
				"Spark cluster", exploratoryName).stream()
				.filter(clusterName -> {
					Optional<SchedulerJobDTO> schedulerJob =
							schedulerJobDAO.fetchSingleSchedulerJobForCluster(user, exploratoryName, clusterName);
					return !schedulerJob.isPresent() || schedulerJob.get().isSyncStartRequired();
				}).collect(Collectors.toList());
	}

	/**
	 * Enriches existing scheduler job with the following data:
	 * - sets current date as 'beginDate' if this parameter wasn't defined;
	 * - sets '9999-12-31' as 'finishDate' if this parameter wasn't defined;
	 * - sets repeating days of existing scheduler job to all days of week if this parameter wasn't defined;
	 * - sets '9999-12-31 00:00' as 'terminateDateTime' if this parameter wasn't defined;
	 * - sets current system time zone offset as 'timeZoneOffset' if this parameter wasn't defined.
	 *
	 * @param dto current scheduler job
	 */
	private void enrichSchedulerJobIfNecessary(SchedulerJobDTO dto) {
		if (Objects.isNull(dto.getBeginDate()) || StringUtils.isBlank(dto.getBeginDate().toString())) {
			dto.setBeginDate(LocalDate.now());
		}
		if (Objects.isNull(dto.getFinishDate()) || StringUtils.isBlank(dto.getFinishDate().toString())) {
			dto.setFinishDate(LocalDate.of(9999, 12, 31));
		}
		if (Objects.isNull(dto.getDaysRepeat()) || dto.getDaysRepeat().isEmpty()) {
			dto.setDaysRepeat(Arrays.asList(DayOfWeek.values()));
		}
		if (Objects.isNull(dto.getTerminateDateTime()) || StringUtils.isBlank(dto.getTerminateDateTime().toString())) {
			dto.setTerminateDateTime(LocalDateTime.of(9999, 12, 31, 0, 0));
		}
		if (Objects.isNull(dto.getTimeZoneOffset()) || StringUtils.isBlank(dto.getTimeZoneOffset().toString())) {
			dto.setTimeZoneOffset(OffsetDateTime.now(ZoneId.systemDefault()).getOffset());
		}
	}

	private void checkExploratoryStatusOrElseThrowException(String user, String exploratoryName) {
		final UserInstanceDTO userInstance = exploratoryDAO.fetchExploratoryFields(user, exploratoryName);
		checkResourceStatusOrElseThrowException(userInstance.getStatus());
	}

	private void checkComputationalStatusOrElseThrowException(String user, String exploratoryName,
															  String computationalName) {
		final UserComputationalResource computationalResource =
				computationalDAO.fetchComputationalFields(user, exploratoryName, computationalName);
		final String computationalStatus = computationalResource.getStatus();
		checkResourceStatusOrElseThrowException(computationalStatus);
	}

	private void checkResourceStatusOrElseThrowException(String resourceStatus) {
		final UserInstanceStatus status = UserInstanceStatus.of(resourceStatus);
		if (Objects.isNull(status) || status.in(UserInstanceStatus.TERMINATED, UserInstanceStatus.TERMINATING,
				UserInstanceStatus.FAILED)) {
			throw new ResourceInappropriateStateException(String.format("Can not create/update scheduler for user " +
					"instance with status: %s", status));
		}
	}
}

