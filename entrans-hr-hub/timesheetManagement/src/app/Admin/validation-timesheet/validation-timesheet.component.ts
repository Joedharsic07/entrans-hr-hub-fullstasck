import { Component } from '@angular/core';
import { ServiceService } from '../Service/service.service';
import { ToastrService } from 'ngx-toastr';

interface Entry {
  top_status?: any;
  user_id: number;
  user_name: string;
  project_id: number;
  project_name: string;
  selected?: boolean;
  loading?: boolean;
  status?: 'success' | 'error';
  error?: string;
  result?: any;
  validation_status?: string;
  timesheet_validations?: any[];
  needs_rerun?: boolean;
  emailLoading?: boolean;
}

@Component({
  selector: 'app-validation-timesheet',
  templateUrl: './validation-timesheet.component.html',
  styleUrl: './validation-timesheet.component.css'
})
export class ValidationTimesheetComponent {
  data: Entry[] = [];
  selectedMonth = new Date().toISOString().slice(0, 7);
  loading = false;
  selectAll = false;

  constructor(private timesheetService: ServiceService, private toastrservice: ToastrService) {}

  ngOnInit() {
    this.fetchData();
  }

  fetchData() {
     const [year, month] = this.selectedMonth.split('-');
    this.timesheetService.getUserProjects(month, year).subscribe(res => {
      const items: Entry[] = [];

      const processUser = (user: any) => {
        user.projects.forEach((proj: any) => {
          const validations = proj.timesheet_validations || [];

          const hasChanges = validations.some((entry: any) => entry.changed === true);

          const errorFlags = validations
            .filter((entry: any) => entry.Status === 'Invalid' && entry.Flag)
            .map((entry: any) => this.formatEntryFlag(entry));

          items.push({
            user_id: user.user_id,
            user_name: user.user_name,
            project_id: proj.project_id,
            project_name: proj.project_name,
            validation_status: proj.validation_status,
            selected: false,
            needs_rerun: hasChanges,
            error: errorFlags.length > 0 ? errorFlags.join('\n') : undefined
          });
        });
      };

      Array.isArray(res) ? res.forEach(processUser) : processUser(res);
      this.data = items;
    });
  }
  validateEntry(entry: Entry) {
    if (!this.selectedMonth) return;
    entry.loading = true;
    entry.status = undefined;
    entry.error = undefined;

    const [year, month] = this.selectedMonth.split('-');
    const payload = {
      user_project_map: { [entry.user_id]: [entry.project_id] },
      month,
      year
    };

    this.timesheetService.validationTimesheet(payload).subscribe(
      () => {
        entry.result = 'Validated';
        entry.status = 'success';
        entry.loading = false;
      },
      err => {
        entry.error = err.error?.error || 'Validation failed';
        entry.status = 'error';
        entry.loading = false;
      }
    );
  }

toggleSelectAll() {
    this.data.forEach(e => (e.selected = this.selectAll));
  }

  onRowCheckboxChange() {
    this.selectAll = this.data.length > 0 && this.data.every(e => e.selected);
  }

  formatEntryFlag(entry: any): string {
  const date = entry.Date || entry.date;
  const flag = entry.Flag || '';

  const isTimesheetMissing = /no\s+timesheet/i.test(flag);

  if (!date || isTimesheetMissing) {
    return flag;
  }

  return `${date}: ${flag}`;
}

 validateSelected() {
  if (!this.selectedMonth) return;
  const [year, month] = this.selectedMonth.split('-');

  const map: any = {};
  this.data.forEach(e => {
    if (e.selected) {
      e.loading = true;
      e.status = undefined;
      e.error = undefined;
      map[e.user_id] = map[e.user_id] || [];
      map[e.user_id].push(e.project_id);
    }
  });

  if (!Object.keys(map).length) return;

  this.loading = true;
  this.timesheetService.validationTimesheet({ user_project_map: map, month, year })
    .subscribe(
      res => {
       const topStatus = res.status;

        this.data.forEach(e => {
          if (e.selected) {
            const uid = e.user_id;
            const pid = e.project_id;
            const validated = res.validated_data?.[uid]?.[pid] || [];

            const summary = res.validation_summary?.[uid]?.[pid] || [];

            const hasInvalidSummary = summary.some((s: any) => s.Status === 'Invalid');

            const invalidEntries = validated.filter((entry: any) => entry.Status === 'Invalid');

            e.result = `${validated.length} entries`;
            e.status = 'success';
            e.top_status = topStatus;
            if (hasInvalidSummary || invalidEntries.length > 0) {
              e.status = 'error';

              const summaryFlags = summary
                .filter((s: any) => s.Status === 'Invalid' && s.Flag)
                .map((s: any) => s.Flag);

              const entryFlags = invalidEntries.map((entry: any) => this.formatEntryFlag(entry));

              e.error = [...summaryFlags, ...entryFlags].join('\n') || 'Validation issues found.';
            } else {
              e.status = 'success';
              e.error = '';
            }

            e.loading = false;
          }
        });

        this.loading = false;
        this.fetchData();
      },
      err => {
        this.data.forEach(e => {
          if (e.selected) {
            e.error = err.error?.error || 'Validation failed';
            e.status = 'error';
            e.loading = false;
          }
        });
        this.loading = false;
      }
    );
}

pushEmail(entry: Entry) {
  if (!this.selectedMonth) return;

  const [year, month] = this.selectedMonth.split('-');

  entry.emailLoading = true;
  const payload = {
    user_project_map: {
      [entry.user_id]: [entry.project_id]
    },
    month,
    year
  };

  this.timesheetService.pushEmail(payload).subscribe({
    next: () => {
      entry.emailLoading = false;
      this.toastrservice.success(
        `Email pushed to ${entry.user_name} for project "${entry.project_name}"`,
        '',
        {
          toastClass: 'ngx-toastr custom-toast',
        }
      );
     
    },
    error: (err) => {
      entry.emailLoading = false;
      this.toastrservice.error('Failed to send email.' ,
        '',
        {
          toastClass: 'ngx-toastr custom-toast',
        }
      )
    }
  });
}
hasSelection(): boolean {
  return this.data.some(e => e.selected);
}
}
