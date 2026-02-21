#include <gtk/gtk.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>

typedef struct {
    GtkApplicationWindow *window;
    GtkBox *root;
    GtkBox *main_hbox;
    GtkBox *right_vbox;
    GtkBox *activity_bar;
    GtkBox *sidebar;
    GtkStack *side_stack;
    GtkTextView *text_view;
    GtkTextBuffer *text_buffer;
    GtkTextView *term_view;
    GtkTextBuffer *term_buffer;
    GtkBox *term_container;
    GtkLabel *tab_label;
    GtkListStore *file_store;
    GHashTable *activity_buttons;
    
    gchar *current_path;
    int shell_fd_in;
    int shell_fd_out;
    pid_t shell_pid;
    GIOChannel *shell_channel;
} LiteCodeApp;

/* CSS стили в стиле VS Code */
static const gchar *CSS_DATA = 
    "window { background-color: #1e1e1e; }\n"
    ".vs-toolbar { background-color: #2d2d30; border-bottom: 1px solid #3f3f46; padding: 4px; }\n"
    ".vs-tool-btn { background: transparent; border: none; color: #f1f1f1; padding: 6px; border-radius: 3px; }\n"
    ".vs-tool-btn:hover { background-color: #3e3e40; }\n"
    ".vs-activity-bar { background-color: #333333; border-right: 1px solid #252526; }\n"
    ".vs-act-btn { padding: 15px; border: none; background: transparent; color: #858585; }\n"
    ".vs-act-btn.active { color: #007acc; border-left: 2px solid #007acc; background-color: #252526; }\n"
    ".vs-sidebar { background-color: #252526; border-right: 1px solid #3f3f46; color: #cccccc; }\n"
    ".file-tree { background-color: #252526; color: #cccccc; font-size: 9pt; }\n"
    "textview { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Monospace'; font-size: 11pt; }\n"
    ".terminal-container { background-color: #0c0c0c; border-top: 1px solid #007acc; }\n"
    ".terminal-view { font-family: 'Monospace'; font-size: 10pt; color: #ffffff; background-color: #0c0c0c; }\n"
    ".vs-status-bar { background-color: #007acc; color: white; padding: 2px 5px; font-size: 9pt; }\n"
    ".status-btn { background: transparent; border: none; color: white; padding: 2px 10px; font-size: 8pt; }\n"
    ".status-btn:hover { background-color: #1f8ad2; }\n";

/* Forward declarations */
static gboolean on_shell_output(GIOChannel *channel, G_GNUC_UNUSED GIOCondition condition, gpointer user_data);
static void on_open_done(GtkFileDialog *dialog, GAsyncResult *result, gpointer user_data);
static void on_save_done(GtkFileDialog *dialog, GAsyncResult *result, gpointer user_data);
static void load_file(LiteCodeApp *app, const gchar *path);
static void save_file(LiteCodeApp *app, const gchar *path);
static void refresh_explorer(LiteCodeApp *app);
static void on_new(G_GNUC_UNUSED GtkButton *button, gpointer user_data);
static void on_open(G_GNUC_UNUSED GtkButton *button, gpointer user_data);
static void on_save(G_GNUC_UNUSED GtkButton *button, gpointer user_data);
static void on_run(G_GNUC_UNUSED GtkButton *button, gpointer user_data);
static void on_side_switch(GtkButton *button, gpointer user_data);
static void toggle_terminal(G_GNUC_UNUSED GtkButton *button, gpointer user_data);
static gboolean on_term_key_pressed(G_GNUC_UNUSED GtkEventControllerKey *controller, 
                                    guint keyval, G_GNUC_UNUSED guint keycode, 
                                    G_GNUC_UNUSED GdkModifierType state, gpointer user_data);
static gboolean on_key_pressed(G_GNUC_UNUSED GtkEventControllerKey *controller, 
                              guint keyval, G_GNUC_UNUSED guint keycode, 
                              GdkModifierType state, gpointer user_data);
static void on_file_activated(GtkTreeView *tree_view, GtkTreePath *path, 
                             G_GNUC_UNUSED GtkTreeViewColumn *column, gpointer user_data);
static void create_toolbar(LiteCodeApp *app);
static void create_activity_bar(LiteCodeApp *app);
static void create_sidebar(LiteCodeApp *app);
static void create_editor_area(LiteCodeApp *app);
static void create_terminal_area(LiteCodeApp *app);
static void create_status_bar(LiteCodeApp *app);
static void init_shell(LiteCodeApp *app);

/* Инициализация shell */
static void init_shell(LiteCodeApp *app) {
    int stdin_pipe[2], stdout_pipe[2];
    
    if (pipe(stdin_pipe) == -1 || pipe(stdout_pipe) == -1) {
        perror("pipe");
        return;
    }
    
    app->shell_pid = fork();
    
    if (app->shell_pid == 0) {
        /* Дочерний процесс */
        dup2(stdin_pipe[0], STDIN_FILENO);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        dup2(stdout_pipe[1], STDERR_FILENO);
        
        close(stdin_pipe[0]);
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);
        close(stdout_pipe[1]);
        
        execl("/bin/sh", "sh", NULL);
        exit(1);
    } else if (app->shell_pid > 0) {
        /* Родительский процесс */
        close(stdin_pipe[0]);
        close(stdout_pipe[1]);
        
        app->shell_fd_in = stdin_pipe[1];
        app->shell_fd_out = stdout_pipe[0];
        
        fcntl(app->shell_fd_out, F_SETFL, O_NONBLOCK);
        
        app->shell_channel = g_io_channel_unix_new(app->shell_fd_out);
        g_io_add_watch(app->shell_channel, G_IO_IN, 
                      (GIOFunc)on_shell_output, app);
    }
}

/* Обработчик вывода shell */
static gboolean on_shell_output(GIOChannel *channel, G_GNUC_UNUSED GIOCondition condition, 
                                gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    gchar buffer[256];
    gsize bytes_read;
    GError *error = NULL;
    
    if (g_io_channel_read_chars(channel, buffer, sizeof(buffer) - 1, 
                                &bytes_read, &error) == G_IO_STATUS_NORMAL) {
        buffer[bytes_read] = '\0';
        
        if (app->term_buffer) {
            GtkTextIter end_iter;
            gtk_text_buffer_get_end_iter(app->term_buffer, &end_iter);
            gtk_text_buffer_insert(app->term_buffer, &end_iter, buffer, -1);
        }
    }
    
    if (error) {
        g_error_free(error);
    }
    
    return TRUE;
}

/* Загрузка файла */
static void load_file(LiteCodeApp *app, const gchar *path) {
    GError *error = NULL;
    gchar *content;
    gsize length;
    
    if (!app || !app->text_buffer) {
        return;
    }
    
    if (!g_file_get_contents(path, &content, &length, &error)) {
        g_warning("Cannot load file: %s", error->message);
        g_error_free(error);
        return;
    }
    
    gtk_text_buffer_set_text(app->text_buffer, content, length);
    if (app->current_path) g_free(app->current_path);
    app->current_path = g_strdup(path);
    
    if (app->tab_label) {
        gchar *basename = g_path_get_basename(path);
        gtk_label_set_text(app->tab_label, basename);
        g_free(basename);
    }
    g_free(content);
}

/* Сохранение файла */
static void save_file(LiteCodeApp *app, const gchar *path) {
    GError *error = NULL;
    GtkTextIter start, end;
    gchar *content;
    
    if (!app || !app->text_buffer) {
        return;
    }
    
    gtk_text_buffer_get_bounds(app->text_buffer, &start, &end);
    content = gtk_text_buffer_get_text(app->text_buffer, &start, &end, FALSE);
    
    if (!g_file_set_contents(path, content, -1, &error)) {
        g_warning("Cannot save file: %s", error->message);
        g_error_free(error);
        g_free(content);
        return;
    }
    
    if (app->current_path) g_free(app->current_path);
    app->current_path = g_strdup(path);
    
    if (app->tab_label) {
        gchar *basename = g_path_get_basename(path);
        gtk_label_set_text(app->tab_label, basename);
        g_free(basename);
    }
    g_free(content);
}

/* Обновление списка файлов в explorer */
static void refresh_explorer(LiteCodeApp *app) {
    GDir *dir;
    const gchar *filename;
    GError *error = NULL;
    
    if (!app || !app->file_store) {
        return;
    }
    
    gtk_list_store_clear(app->file_store);
    
    dir = g_dir_open(".", 0, &error);
    if (!dir) {
        g_warning("Cannot open directory: %s", error->message);
        g_error_free(error);
        return;
    }
    
    GList *files = NULL;
    while ((filename = g_dir_read_name(dir))) {
        if (g_file_test(filename, G_FILE_TEST_IS_REGULAR)) {
            files = g_list_prepend(files, g_strdup(filename));
        }
    }
    files = g_list_sort(files, (GCompareFunc)strcmp);
    
    for (GList *l = files; l != NULL; l = l->next) {
        gchar *absolute_path = g_build_filename(g_get_current_dir(), l->data, NULL);
        GtkTreeIter iter;
        gtk_list_store_append(app->file_store, &iter);
        gtk_list_store_set(app->file_store, &iter, 0, l->data, 1, absolute_path, -1);
        g_free(absolute_path);
        g_free(l->data);
    }
    
    g_list_free(files);
    g_dir_close(dir);
}

/* Обработчик кнопок в toolbar */
static void on_new(G_GNUC_UNUSED GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !app->text_buffer) return;
    
    gtk_text_buffer_set_text(app->text_buffer, "", 0);
    if (app->current_path) {
        g_free(app->current_path);
        app->current_path = NULL;
    }
    if (app->tab_label) {
        gtk_label_set_text(app->tab_label, "untitled.py");
    }
}

static void on_open(G_GNUC_UNUSED GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !app->window) return;
    
    GtkFileDialog *dialog = gtk_file_dialog_new();
    gtk_file_dialog_open(dialog, GTK_WINDOW(app->window), NULL, 
                        (GAsyncReadyCallback)on_open_done, app);
}

static void on_open_done(GtkFileDialog *dialog, GAsyncResult *result, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    GFile *file = gtk_file_dialog_open_finish(dialog, result, NULL);
    if (file && app) {
        load_file(app, g_file_get_path(file));
        g_object_unref(file);
    }
    if (dialog) g_object_unref(dialog);
}

static void on_save(G_GNUC_UNUSED GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app) return;
    
    if (!app->current_path) {
        if (!app->window) return;
        GtkFileDialog *dialog = gtk_file_dialog_new();
        gtk_file_dialog_save(dialog, GTK_WINDOW(app->window), NULL, 
                            (GAsyncReadyCallback)on_save_done, app);
    } else {
        save_file(app, app->current_path);
        refresh_explorer(app);
    }
}

static void on_save_done(GtkFileDialog *dialog, GAsyncResult *result, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    GFile *file = gtk_file_dialog_save_finish(dialog, result, NULL);
    if (file && app) {
        save_file(app, g_file_get_path(file));
        refresh_explorer(app);
        g_object_unref(file);
    }
    if (dialog) g_object_unref(dialog);
}

static void on_run(G_GNUC_UNUSED GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !app->current_path) return;
    
    if (app->term_container) {
        gtk_widget_set_visible(GTK_WIDGET(app->term_container), TRUE);
    }
    if (app->term_view) {
        gtk_widget_grab_focus(GTK_WIDGET(app->term_view));
    }
    
    gchar *cmd = g_strdup_printf("python3 %s\n", app->current_path);
    if (app->shell_fd_in > 0) {
        write(app->shell_fd_in, cmd, strlen(cmd));
    }
    g_free(cmd);
}

/* Обработчик переключения боковых панелей */
static void on_side_switch(GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !button) return;
    
    const gchar *name = g_object_get_data(G_OBJECT(button), "panel-name");
    if (!name) return;
    
    if (app->side_stack) {
        gtk_stack_set_visible_child_name(app->side_stack, name);
    }
    
    if (app->activity_buttons) {
        GHashTableIter iter;
        gpointer key, value;
        g_hash_table_iter_init(&iter, app->activity_buttons);
        while (g_hash_table_iter_next(&iter, &key, &value)) {
            gtk_widget_remove_css_class(GTK_WIDGET(value), "active");
        }
    }
    gtk_widget_add_css_class(GTK_WIDGET(button), "active");
}

/* Переключение терминала */
static void toggle_terminal(G_GNUC_UNUSED GtkButton *button, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !app->term_container) return;
    
    gboolean visible = gtk_widget_get_visible(GTK_WIDGET(app->term_container));
    gtk_widget_set_visible(GTK_WIDGET(app->term_container), !visible);
    
    if (!visible && app->term_view) {
        gtk_widget_grab_focus(GTK_WIDGET(app->term_view));
    }
}

/* Обработчик нажатия клавиш в терминале */
static gboolean on_term_key_pressed(G_GNUC_UNUSED GtkEventControllerKey *controller, 
                                    guint keyval, G_GNUC_UNUSED guint keycode, 
                                    G_GNUC_UNUSED GdkModifierType state, 
                                    gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !app->term_buffer) return GDK_EVENT_PROPAGATE;
    
    if (keyval == GDK_KEY_Return) {
        GtkTextIter start, end;
        gint line_count = gtk_text_buffer_get_line_count(app->term_buffer);
        
        gtk_text_buffer_get_iter_at_line(app->term_buffer, &start, line_count - 1);
        gtk_text_buffer_get_end_iter(app->term_buffer, &end);
        
        gchar *line_text = gtk_text_buffer_get_text(app->term_buffer, &start, &end, FALSE);
        
        /* Очистка и выполнение команды */
        gchar *cmd = g_strdup_printf("%s\n", g_strstrip(line_text));
        if (app->shell_fd_in > 0) {
            write(app->shell_fd_in, cmd, strlen(cmd));
        }
        
        g_free(cmd);
        g_free(line_text);
        return GDK_EVENT_STOP;
    }
    return GDK_EVENT_PROPAGATE;
}

/* Обработчик глобальных клавиш */
static gboolean on_key_pressed(G_GNUC_UNUSED GtkEventControllerKey *controller, 
                              guint keyval, G_GNUC_UNUSED guint keycode, 
                              GdkModifierType state, 
                              gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app) return GDK_EVENT_PROPAGATE;
    
    if (state & GDK_CONTROL_MASK) {
        switch (keyval) {
            case GDK_KEY_s:
                on_save(NULL, app);
                return GDK_EVENT_STOP;
            case GDK_KEY_o:
                on_open(NULL, app);
                return GDK_EVENT_STOP;
            case GDK_KEY_n:
                on_new(NULL, app);
                return GDK_EVENT_STOP;
            case GDK_KEY_grave:
                toggle_terminal(NULL, app);
                return GDK_EVENT_STOP;
        }
    }
    return GDK_EVENT_PROPAGATE;
}

/* Обработчик выбора файла в explorer */
static void on_file_activated(GtkTreeView *tree_view, GtkTreePath *path, 
                             G_GNUC_UNUSED GtkTreeViewColumn *column, gpointer user_data) {
    LiteCodeApp *app = (LiteCodeApp *)user_data;
    if (!app || !tree_view) return;
    
    GtkTreeIter iter;
    gchar *file_path = NULL;
    
    gtk_tree_model_get_iter(gtk_tree_view_get_model(tree_view), &iter, path);
    gtk_tree_model_get(gtk_tree_view_get_model(tree_view), &iter, 1, &file_path, -1);
    
    if (file_path) {
        load_file(app, file_path);
        g_free(file_path);
    }
}

/* Создание toolbar */
static void create_toolbar(LiteCodeApp *app) {
    if (!app || !app->root) return;
    
    GtkBox *tb = GTK_BOX(gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0));
    gtk_widget_add_css_class(GTK_WIDGET(tb), "vs-toolbar");
    
    struct {
        const gchar *icon;
        GCallback callback;
    } buttons[] = {
        {"document-new-symbolic", G_CALLBACK(on_new)},
        {"document-open-symbolic", G_CALLBACK(on_open)},
        {"document-save-symbolic", G_CALLBACK(on_save)},
        {"media-playback-start-symbolic", G_CALLBACK(on_run)},
        {NULL, NULL}
    };
    
    for (int i = 0; buttons[i].icon; i++) {
        GtkButton *btn = GTK_BUTTON(gtk_button_new_from_icon_name(buttons[i].icon));
        gtk_widget_add_css_class(GTK_WIDGET(btn), "vs-tool-btn");
        g_signal_connect(btn, "clicked", buttons[i].callback, app);
        gtk_box_append(tb, GTK_WIDGET(btn));
    }
    
    gtk_box_append(app->root, GTK_WIDGET(tb));
}

/* Создание activity bar */
static void create_activity_bar(LiteCodeApp *app) {
    if (!app || !app->main_hbox) return;
    
    app->activity_bar = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    gtk_widget_add_css_class(GTK_WIDGET(app->activity_bar), "vs-activity-bar");
    app->activity_buttons = g_hash_table_new(g_str_hash, g_str_equal);
    
    struct {
        const gchar *icon;
        const gchar *name;
    } items[] = {
        {"system-file-manager-symbolic", "explorer"},
        {"edit-find-symbolic", "search"},
        {"emblem-system-symbolic", "settings"},
        {NULL, NULL}
    };
    
    for (int i = 0; items[i].icon; i++) {
        GtkButton *btn = GTK_BUTTON(gtk_button_new_from_icon_name(items[i].icon));
        gtk_widget_add_css_class(GTK_WIDGET(btn), "vs-act-btn");
        
        g_object_set_data(G_OBJECT(btn), "panel-name", (gpointer)items[i].name);
        g_signal_connect(btn, "clicked", G_CALLBACK(on_side_switch), app);
        
        gtk_box_append(app->activity_bar, GTK_WIDGET(btn));
        g_hash_table_insert(app->activity_buttons, (gpointer)items[i].name, btn);
    }
    
    GtkButton *explorer_btn = g_hash_table_lookup(app->activity_buttons, "explorer");
    if (explorer_btn) {
        gtk_widget_add_css_class(GTK_WIDGET(explorer_btn), "active");
    }
    
    gtk_box_append(app->main_hbox, GTK_WIDGET(app->activity_bar));
}

/* Создание sidebar */
static void create_sidebar(LiteCodeApp *app) {
    if (!app || !app->main_hbox) return;
    
    app->sidebar = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    gtk_widget_add_css_class(GTK_WIDGET(app->sidebar), "vs-sidebar");
    gtk_widget_set_size_request(GTK_WIDGET(app->sidebar), 240, -1);
    
    app->side_stack = GTK_STACK(gtk_stack_new());
    gtk_box_append(app->sidebar, GTK_WIDGET(app->side_stack));
    
    /* Explorer */
    GtkBox *exp = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    GtkLabel *exp_label = GTK_LABEL(gtk_label_new("EXPLORER"));
    gtk_label_set_xalign(exp_label, 0);
    gtk_widget_set_margin_start(GTK_WIDGET(exp_label), 15);
    gtk_widget_set_margin_top(GTK_WIDGET(exp_label), 10);
    gtk_box_append(exp, GTK_WIDGET(exp_label));
    
    app->file_store = gtk_list_store_new(2, G_TYPE_STRING, G_TYPE_STRING);
    GtkTreeView *tree = GTK_TREE_VIEW(gtk_tree_view_new_with_model(
        GTK_TREE_MODEL(app->file_store)));
    gtk_widget_add_css_class(GTK_WIDGET(tree), "file-tree");
    gtk_tree_view_set_headers_visible(tree, FALSE);
    
    GtkCellRenderer *renderer = gtk_cell_renderer_text_new();
    GtkTreeViewColumn *column = gtk_tree_view_column_new_with_attributes(
        "", renderer, "text", 0, NULL);
    gtk_tree_view_append_column(tree, column);
    g_signal_connect(tree, "row-activated", G_CALLBACK(on_file_activated), app);
    
    GtkScrolledWindow *scroll = GTK_SCROLLED_WINDOW(gtk_scrolled_window_new());
    gtk_scrolled_window_set_child(scroll, GTK_WIDGET(tree));
    gtk_widget_set_vexpand(GTK_WIDGET(scroll), TRUE);
    gtk_box_append(exp, GTK_WIDGET(scroll));
    gtk_stack_add_named(app->side_stack, GTK_WIDGET(exp), "explorer");
    
    /* Search */
    GtkBox *search = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    GtkLabel *search_label = GTK_LABEL(gtk_label_new("SEARCH"));
    gtk_label_set_xalign(search_label, 0);
    gtk_widget_set_margin_start(GTK_WIDGET(search_label), 15);
    gtk_widget_set_margin_top(GTK_WIDGET(search_label), 10);
    gtk_box_append(search, GTK_WIDGET(search_label));
    
    GtkEntry *s_entry = GTK_ENTRY(gtk_entry_new());
    gtk_entry_set_placeholder_text(s_entry, "Find...");
    gtk_widget_set_margin_start(GTK_WIDGET(s_entry), 10);
    gtk_widget_set_margin_end(GTK_WIDGET(s_entry), 10);
    gtk_widget_set_margin_top(GTK_WIDGET(s_entry), 10);
    gtk_box_append(search, GTK_WIDGET(s_entry));
    gtk_stack_add_named(app->side_stack, GTK_WIDGET(search), "search");
    
    /* Settings */
    GtkBox *sett = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    GtkLabel *sett_label = GTK_LABEL(gtk_label_new("SETTINGS"));
    gtk_label_set_xalign(sett_label, 0);
    gtk_widget_set_margin_start(GTK_WIDGET(sett_label), 15);
    gtk_widget_set_margin_top(GTK_WIDGET(sett_label), 10);
    gtk_box_append(sett, GTK_WIDGET(sett_label));
    
    GtkCheckButton *cb = GTK_CHECK_BUTTON(gtk_check_button_new_with_label("Auto Save"));
    gtk_widget_set_margin_start(GTK_WIDGET(cb), 15);
    gtk_widget_set_margin_top(GTK_WIDGET(cb), 10);
    gtk_box_append(sett, GTK_WIDGET(cb));
    gtk_stack_add_named(app->side_stack, GTK_WIDGET(sett), "settings");
    
    gtk_box_append(app->main_hbox, GTK_WIDGET(app->sidebar));
    refresh_explorer(app);
}

/* Создание области редактора */
static void create_editor_area(LiteCodeApp *app) {
    if (!app || !app->right_vbox) return;
    
    app->tab_label = GTK_LABEL(gtk_label_new("welcome.py"));
    gtk_label_set_xalign(app->tab_label, 0);
    gtk_widget_set_margin_start(GTK_WIDGET(app->tab_label), 15);
    gtk_box_append(app->right_vbox, GTK_WIDGET(app->tab_label));
    
    GtkScrolledWindow *scroll = GTK_SCROLLED_WINDOW(gtk_scrolled_window_new());
    gtk_widget_set_vexpand(GTK_WIDGET(scroll), TRUE);
    
    app->text_view = GTK_TEXT_VIEW(gtk_text_view_new());
    app->text_buffer = gtk_text_view_get_buffer(app->text_view);
    gtk_scrolled_window_set_child(scroll, GTK_WIDGET(app->text_view));
    gtk_box_append(app->right_vbox, GTK_WIDGET(scroll));
}

/* Создание области терминала */
static void create_terminal_area(LiteCodeApp *app) {
    if (!app || !app->right_vbox) return;
    
    app->term_container = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    gtk_widget_add_css_class(GTK_WIDGET(app->term_container), "terminal-container");
    gtk_widget_set_size_request(GTK_WIDGET(app->term_container), -1, 200);
    gtk_widget_set_visible(GTK_WIDGET(app->term_container), FALSE);
    
    GtkScrolledWindow *scroll = GTK_SCROLLED_WINDOW(gtk_scrolled_window_new());
    gtk_widget_set_vexpand(GTK_WIDGET(scroll), TRUE);
    
    app->term_view = GTK_TEXT_VIEW(gtk_text_view_new());
    app->term_buffer = gtk_text_view_get_buffer(app->term_view);
    gtk_widget_add_css_class(GTK_WIDGET(app->term_view), "terminal-view");
    
    GtkEventControllerKey *term_ctrl = GTK_EVENT_CONTROLLER_KEY(
        gtk_event_controller_key_new());
    g_signal_connect(term_ctrl, "key-pressed", G_CALLBACK(on_term_key_pressed), app);
    gtk_widget_add_controller(GTK_WIDGET(app->term_view), GTK_EVENT_CONTROLLER(term_ctrl));
    
    gtk_scrolled_window_set_child(scroll, GTK_WIDGET(app->term_view));
    gtk_box_append(app->term_container, GTK_WIDGET(scroll));
    gtk_box_append(app->right_vbox, GTK_WIDGET(app->term_container));
}

/* Создание статус-бара */
static void create_status_bar(LiteCodeApp *app) {
    if (!app || !app->root) return;
    
    GtkBox *sb = GTK_BOX(gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0));
    gtk_widget_add_css_class(GTK_WIDGET(sb), "vs-status-bar");
    
    GtkButton *term_toggle = GTK_BUTTON(gtk_button_new_with_label("Terminal"));
    gtk_widget_add_css_class(GTK_WIDGET(term_toggle), "status-btn");
    g_signal_connect(term_toggle, "clicked", G_CALLBACK(toggle_terminal), app);
    gtk_box_append(sb, GTK_WIDGET(term_toggle));
    
    gtk_box_append(app->root, GTK_WIDGET(sb));
}

/* Инициализация приложения */
static void app_activate(GtkApplication *gtk_app, G_GNUC_UNUSED gpointer user_data) {
    LiteCodeApp *app = g_new0(LiteCodeApp, 1);
    
    if (!app) {
        g_error("Failed to allocate memory for LiteCodeApp");
        return;
    }
    
    app->window = GTK_APPLICATION_WINDOW(
        gtk_application_window_new(gtk_app));
    
    if (!app->window) {
        g_error("Failed to create application window");
        g_free(app);
        return;
    }
    
    gtk_window_set_title(GTK_WINDOW(app->window), "LiteCode");
    gtk_window_set_default_size(GTK_WINDOW(app->window), 1100, 700);
    
    /* Загрузка CSS */
    GtkCssProvider *provider = gtk_css_provider_new();
    if (provider) {
        gtk_css_provider_load_from_data(provider, CSS_DATA, -1);
        gtk_style_context_add_provider_for_display(
            gdk_display_get_default(),
            GTK_STYLE_PROVIDER(provider),
            GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    }
    
    /* Создание основного контейнера */
    app->root = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    gtk_window_set_child(GTK_WINDOW(app->window), GTK_WIDGET(app->root));
    
    create_toolbar(app);
    
    app->main_hbox = GTK_BOX(gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0));
    gtk_widget_set_vexpand(GTK_WIDGET(app->main_hbox), TRUE);
    gtk_box_append(app->root, GTK_WIDGET(app->main_hbox));
    
    create_activity_bar(app);
    create_sidebar(app);
    
    app->right_vbox = GTK_BOX(gtk_box_new(GTK_ORIENTATION_VERTICAL, 0));
    gtk_widget_set_hexpand(GTK_WIDGET(app->right_vbox), TRUE);
    gtk_box_append(app->main_hbox, GTK_WIDGET(app->right_vbox));
    
    create_editor_area(app);
    create_terminal_area(app);
    create_status_bar(app);
    
    /* Инициализация shell */
    init_shell(app);
    
    /* Регистрация клавиш */
    GtkEventControllerKey *key_ctrl = GTK_EVENT_CONTROLLER_KEY(
        gtk_event_controller_key_new());
    g_signal_connect(key_ctrl, "key-pressed", G_CALLBACK(on_key_pressed), app);
    gtk_widget_add_controller(GTK_WIDGET(app->window), 
                             GTK_EVENT_CONTROLLER(key_ctrl));
    
    gtk_window_present(GTK_WINDOW(app->window));
}

/* Точка входа */
int main(int argc, char *argv[]) {
    GtkApplication *app = gtk_application_new(
        "com.litecode.app", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(app, "activate", G_CALLBACK(app_activate), NULL);
    int status = g_application_run(G_APPLICATION(app), argc, argv);
    g_object_unref(app);
    return status;
}
