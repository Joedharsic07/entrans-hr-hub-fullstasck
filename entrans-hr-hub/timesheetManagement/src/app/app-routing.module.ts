import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LoginComponent } from './component/login/login.component';
import { SignupComponent } from './component/signup/signup.component';
import { TimesheetComponent } from './timesheet/timesheet/timesheet.component';
import { AdminComponent } from './Admin/admin/admin.component';
import { TimesheetAutomationComponent } from './Admin/timesheetauto/timesheet-automation/timesheet-automation.component';
import { PptAutomationComponent } from './Admin/ppt-automation/ppt-automation.component';
import { SidebarComponent } from './Admin/sidebar/sidebar.component';
import { AuthGuard } from './shared/Auth/auth.guard';
import { ResetPasswordComponent } from './component/reset-password/reset-password.component';
import { ConfrimResetPasswordComponent } from './component/confrim-reset-password/confrim-reset-password.component';
import { UserProfileComponent } from './component/user-profile/user-profile.component';
import { UserTimesheetsComponent } from './Admin/user-timesheets/user-timesheets.component';
import { UserTimesheetsListComponent } from './Admin/user-timesheets-list/user-timesheets-list.component';
import { CreateProjectComponent } from './Admin/create-project/create-project.component';
import { ValidationTimesheetComponent } from './Admin/validation-timesheet/validation-timesheet.component';
import { ProjectMembersComponent } from './Admin/project-members/project-members.component';

const routes: Routes = [{
  path: '',
  redirectTo: 'login',
  pathMatch: 'full'
},
{
  path: 'user-profile',
  component: UserProfileComponent,
},
{
  path: 'login',
  component: LoginComponent
},
{
  path: 'signup',
  component: SignupComponent
},
{
  path: 'timesheet/:id',
  component: TimesheetComponent,

},
{
  path: 'admin',
  component: AdminComponent,

},
{
  path: 'timesheet',
  component: TimesheetAutomationComponent,
  canActivate: [AuthGuard],
  data: { roles: ['user', 'Admin'] }
},
{
  path: 'ppt-automation',
  component: PptAutomationComponent,
  canActivate: [AuthGuard],
  data: { roles: ['user', 'Admin'] }
},
{
  path: 'sidebar',
  component: SidebarComponent,
  canActivate: [AuthGuard],
  data: { roles: ['user', 'Admin'] }
},
{
  path: 'password_reset',
  component: ResetPasswordComponent
},
{
  path: 'reset-password',
  component: ConfrimResetPasswordComponent
},
{
  path: 'user-timesheets',
  component: UserTimesheetsComponent,
},
{
  path: 'user-timesheets-list',
  component: UserTimesheetsListComponent,

},
{
  path: 'user-timesheet/:userProjectId/:projectId',
  component: UserTimesheetsListComponent
},
{
  path: 'create-project',
  component: CreateProjectComponent,
  canActivate: [AuthGuard],
  data: { roles: ['user', 'Admin'] }
},
{
  path: 'validation-timesheet',
  component: ValidationTimesheetComponent,
  canActivate: [AuthGuard],
  data: { roles: ['user', 'Admin'] }
},
{
  path: 'project-members',
  component: ProjectMembersComponent,
  canActivate: [AuthGuard],
  data: { roles: ['Admin'] }
}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
