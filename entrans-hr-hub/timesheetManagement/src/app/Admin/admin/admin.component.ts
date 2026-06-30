import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-admin',
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css'
})
export class AdminComponent implements OnInit {
  constructor(private router: Router) {}

  showTimesheetOptions: boolean = false;
  isAdmin: boolean = false;

  role = sessionStorage.getItem('role');

  ngOnInit() {
    if (this.role === 'Admin') this.isAdmin = true;
  }

  navigateToTimesheet() {
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

  navigateToUserTimesheets() {
    this.router.navigate(['/user-timesheets']);
  }

  navigateToCreateProject() {
    this.router.navigate(['/create-project']);
  }

  navigateToProjectMembers() {
    this.router.navigate(['/project-members']);
  }
}
