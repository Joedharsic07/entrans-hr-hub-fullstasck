import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ServiceService } from '../Service/service.service';

@Component({
  selector: 'app-admin',
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css'
})
export class AdminComponent implements OnInit {
  constructor(public router: Router, private service: ServiceService) {}

  showTimesheetOptions: boolean = false;
  isAdmin: boolean = false;

  role = sessionStorage.getItem('role');

  // Non-admin user projects
  userProjects: any[] = [];
  projectsLoading = false;

  ngOnInit() {
    if (this.role === 'Admin') {
      this.isAdmin = true;
    } else {
      this.loadUserProjects();
    }
  }

  loadUserProjects(): void {
    this.projectsLoading = true;
    this.service.userTimesheetlist().subscribe({
      next: (res: any) => {
        this.userProjects = res.projects || [];
        this.projectsLoading = false;
      },
      error: () => { this.projectsLoading = false; }
    });
  }

  navigateToTimesheet(timesheetsLink: string): void {
    this.router.navigate(['/' + timesheetsLink]);
  }

  navigateToTimesheetOptions() {
    this.showTimesheetOptions = true;
  }

  navigateToTimesheet_upload() {
    this.showTimesheetOptions = false;
    this.router.navigate(['/timesheet']);
  }

  navigateToValidationTimesheet() {
    this.showTimesheetOptions = false;
    this.router.navigate(['/validation-timesheet']);
  }

  navigateToPpt() {
    this.router.navigate(['/ppt-automation']);
  }

  navigateToCreateProject() {
    this.router.navigate(['/create-project']);
  }

  navigateToProjectMembers() {
    this.router.navigate(['/project-members']);
  }
}
