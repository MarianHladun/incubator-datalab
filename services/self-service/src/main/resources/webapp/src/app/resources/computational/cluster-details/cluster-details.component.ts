/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

import { Component, ViewChild, OnInit, Inject } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { FormGroup, FormBuilder } from '@angular/forms';
import { ToastrService } from 'ngx-toastr';

import { DateUtils, CheckUtils } from '../../../core/util';
import { DataengineConfigurationService } from '../../../core/services';
import { DICTIONARY } from '../../../../dictionary/global.dictionary';
import { CLUSTER_CONFIGURATION } from '../computational-resource-create-dialog/cluster-configuration-templates';
import {AuditService} from '../../../core/services/audit.service';
import {CopyPathUtils} from '../../../core/util/copyPathUtils';

@Component({
  selector: 'datalab-cluster-details',
  templateUrl: 'cluster-details.component.html',
  styleUrls: ['./cluster-details.component.scss']
})

export class DetailComputationalResourcesComponent implements OnInit {
  readonly DICTIONARY = DICTIONARY;
  readonly PROVIDER = this.data.environment.cloud_provider;

  resource: any;
  environment: any;
  @ViewChild('configurationNode') configuration;

  upTimeInHours: number;
  tooltip: boolean = false;
  config: Array<{}> = [];
  public configurationForm: FormGroup;
  isCopyIconVissible: any = {};
  isCopied: boolean = true;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: any,
    public toastr: ToastrService,
    public dialogRef: MatDialogRef<DetailComputationalResourcesComponent>,
    private dataengineConfigurationService: DataengineConfigurationService,
    private _fb: FormBuilder,
    private auditService: AuditService
  ) { }

  ngOnInit() {
    this.open(this.data.environment, this.data.resource);
  }

  public open(environment, resource): void {
    this.tooltip = false;
    this.resource = resource;
    this.environment = environment;


    this.upTimeInHours = (this.resource.up_time) ? DateUtils.diffBetweenDatesInHours(this.resource.up_time) : 0;
    this.initFormModel();

    if (this.resource.image === 'docker.datalab-dataengine') this.getClusterConfiguration();
  }

  public isEllipsisActive($event): void {
    if ($event.target.offsetWidth < $event.target.scrollWidth)
      this.tooltip = true;
  }

  public selectConfiguration() {
    if (this.configuration.nativeElement.checked) {

      this.configurationForm.controls['configuration_parameters']
        .setValue(JSON.stringify(this.config.length ? this.config : CLUSTER_CONFIGURATION.SPARK, undefined, 2));
    } else {
      this.configurationForm.controls['configuration_parameters'].setValue('');
    }
  }

  public getClusterConfiguration(): void {
    this.dataengineConfigurationService
      .getClusterConfiguration(this.environment.project, this.environment.name, this.resource.computational_name, this.PROVIDER)
      .subscribe((result: any) => this.config = result,
        error => this.toastr.error(error.message || 'Configuration loading failed!', 'Oops!'));
  }

  public editClusterConfiguration(data): void {
    this.dataengineConfigurationService
      .editClusterConfiguration(
        data.configuration_parameters,
        this.environment.project,
        this.environment.name,
        this.resource.computational_name,
        this.PROVIDER
      )
      .subscribe(result => {
        this.dialogRef.close();
      },
        error => this.toastr.error(error.message || 'Edit onfiguration failed!', 'Oops!'));
  }

  private initFormModel(): void {
    this.configurationForm = this._fb.group({
      configuration_parameters: ['', [this.validConfiguration.bind(this)]]
    });
  }

  private validConfiguration(control) {
    if (this.configuration)
      return this.configuration.nativeElement['checked']
        ? (control.value && control.value !== null && CheckUtils.isJSON(control.value) ? null : { valid: false })
        : null;
  }

  public logAction(resource: any, environment, copy?: string) {
    const clusterInfo = {
      action: copy,
      cluster: resource.computational_name,
      notebook: environment.name,
      clusterType: resource.dataEngineType === 'dataengine-service' ? 'Hadoop' : 'Master'
    };

    this.auditService.sendDataToAudit(
      {resource_name: resource.computational_name, info: JSON.stringify(clusterInfo), type: 'COMPUTE'}
      ).subscribe();
  }

  public copyLink(url: string) {
    CopyPathUtils.copyPath(url);
  }

  public showCopyIcon(element) {
    this.isCopyIconVissible[element] = true;
  }
  public hideCopyIcon() {
    for (const key in this.isCopyIconVissible) {
      this.isCopyIconVissible[key] = false;
    }
    this.isCopied = true;
  }
}
