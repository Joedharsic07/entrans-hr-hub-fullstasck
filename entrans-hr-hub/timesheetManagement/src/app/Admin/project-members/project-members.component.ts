import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators';
import { ServiceService } from '../Service/service.service';

interface ProjectUser {
  user_id: number;
  user_name: string;
  email: string;
  role: string;
}

interface ProjectSummary {
  project_id: number;
  project_name: string;
  user_count: number;
}

interface PaginatedProjects {
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  results: ProjectSummary[];
}

interface ProjectDetail {
  project_id: number;
  project_name: string;
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  users: ProjectUser[];
}

@Component({
  selector: 'app-project-members',
  templateUrl: './project-members.component.html',
  styleUrls: ['./project-members.component.css']
})
export class ProjectMembersComponent implements OnInit, OnDestroy {

  // Projects pane
  projectsData: PaginatedProjects = { count: 0, total_pages: 1, current_page: 1, page_size: 10, results: [] };
  projectsLoading = false;
  projectSearch = '';
  projectPage = 1;
  readonly projectPageSize = 10;

  // Users pane
  selectedProject: ProjectSummary | null = null;
  usersData: ProjectDetail | null = null;
  usersLoading = false;
  userSearch = '';
  userPage = 1;
  readonly userPageSize = 12;

  private projectSearch$ = new Subject<string>();
  private userSearch$ = new Subject<string>();
  private destroy$ = new Subject<void>();

  constructor(private service: ServiceService, private router: Router) {}

  ngOnInit(): void {
    this.loadProjects();

    this.projectSearch$.pipe(
      debounceTime(400),
      distinctUntilChanged(),
      takeUntil(this.destroy$)
    ).subscribe(() => {
      this.projectPage = 1;
      this.loadProjects();
    });

    this.userSearch$.pipe(
      debounceTime(400),
      distinctUntilChanged(),
      takeUntil(this.destroy$)
    ).subscribe(() => {
      this.userPage = 1;
      this.loadUsers();
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadProjects(): void {
    this.projectsLoading = true;
    const params: any = { page: this.projectPage, page_size: this.projectPageSize };
    if (this.projectSearch.trim()) params.project_search = this.projectSearch.trim();

    this.service.getProjectUserRoles(params).subscribe({
      next: (res: PaginatedProjects) => {
        this.projectsData = res;
        this.projectsLoading = false;
      },
      error: () => { this.projectsLoading = false; }
    });
  }

  loadUsers(): void {
    if (!this.selectedProject) return;
    this.usersLoading = true;
    const params: any = { page: this.userPage, page_size: this.userPageSize };
    if (this.userSearch.trim()) params.user_search = this.userSearch.trim();

    this.service.getProjectUsers(this.selectedProject.project_id, params).subscribe({
      next: (res: ProjectDetail) => {
        this.usersData = res;
        this.usersLoading = false;
      },
      error: () => { this.usersLoading = false; }
    });
  }

  onProjectSearchChange(): void {
    this.projectSearch$.next(this.projectSearch);
  }

  onUserSearchChange(): void {
    this.userSearch$.next(this.userSearch);
  }

  selectProject(proj: ProjectSummary): void {
    this.selectedProject = proj;
    this.userSearch = '';
    this.userPage = 1;
    this.usersData = null;
    this.loadUsers();
  }

  clearProject(): void {
    this.selectedProject = null;
    this.usersData = null;
    this.userSearch = '';
  }

  clearProjectSearch(): void {
    this.projectSearch = '';
    this.projectPage = 1;
    this.loadProjects();
  }

  clearUserSearch(): void {
    this.userSearch = '';
    this.userPage = 1;
    this.loadUsers();
  }

  goToProjectPage(page: number): void {
    if (page < 1 || page > this.projectsData.total_pages) return;
    this.projectPage = page;
    this.loadProjects();
  }

  goToUserPage(page: number): void {
    if (!this.usersData || page < 1 || page > this.usersData.total_pages) return;
    this.userPage = page;
    this.loadUsers();
  }

  get projectPageNumbers(): number[] {
    const total = this.projectsData.total_pages;
    const cur = this.projectsData.current_page;
    return this.buildPageRange(cur, total);
  }

  get userPageNumbers(): number[] {
    if (!this.usersData) return [];
    return this.buildPageRange(this.usersData.current_page, this.usersData.total_pages);
  }

  private buildPageRange(current: number, total: number): number[] {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages: number[] = [];
    const delta = 2;
    for (let i = 1; i <= total; i++) {
      if (i === 1 || i === total || (i >= current - delta && i <= current + delta)) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== -1) {
        pages.push(-1); // ellipsis marker
      }
    }
    return pages;
  }

  goBack(): void {
    this.router.navigate(['/admin']);
  }
}
